from fastapi import APIRouter, HTTPException
from prometheus_client import Counter, Histogram
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage
import psycopg2
import os, uuid, json, time

router = APIRouter()

quiz_counter = Counter(
    "akilli_sinif_quiz_generated_total",
    "Üretilen quiz sayısı",
    ["topic"]
)

score_histogram = Histogram(
    "akilli_sinif_quiz_scores",
    "Skor dağılımı",
    buckets=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
)

llm_duration = Histogram(
    "akilli_sinif_llm_seconds",
    "LLM yanıt süresi",
    ["operation"]
)

weak_topic_counter = Counter(
    "akilli_sinif_weak_topics_total",
    "Zayıf konu sayacı",
    ["topic"]
)


def get_llm():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY bulunamadı (Kubernetes secret kontrol et)")
    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        google_api_key=api_key,
        temperature=0.7,
    )


def get_query_embeddings():
    """Query için RETRIEVAL_QUERY task_type — embed ile uyumlu olması şart."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY bulunamadı")
    return GoogleGenerativeAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "gemini-embedding-2-preview"),
        task_type="RETRIEVAL_QUERY",
        google_api_key=api_key
    )


def get_vectorstore(student_id: str) -> Chroma:
    """Öğrencinin ChromaDB collection'ına LangChain wrapper ile bağlan."""
    import chromadb
    chroma_client = chromadb.HttpClient(
        host=os.getenv("CHROMA_HOST", "chromadb"),
        port=int(os.getenv("CHROMA_PORT", 8000)),
    )
    return Chroma(
        client=chroma_client,
        collection_name=f"student_{student_id}",
        embedding_function=get_query_embeddings(),
    )


def get_db():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def _parse_json_response(text: str) -> dict:
    clean = (
        text.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return json.loads(clean)


def _query_context(student_id: str, topic: str, n_results: int = 5) -> str:
    """ChromaDB'den ilgili chunk'ları getir."""
    try:
        vectorstore = get_vectorstore(student_id)
        docs = vectorstore.similarity_search(topic, k=n_results)
        return "\n\n".join([doc.page_content for doc in docs])
    except Exception as e:
        print(f"!!! CHROMA QUERY HATASI: {e}")
        return ""


class QuizRequest(BaseModel):
    student_id: str
    topic: str
    question_count: int = 5


@router.post("/quiz/generate")
async def generate_quiz(req: QuizRequest):

    llm = get_llm()

    context = _query_context(req.student_id, req.topic, n_results=5)

    if not context:
        raise HTTPException(404, "Bu konu için ders notu bulunamadı.")

    prompt = f"""
Aşağıdaki ders notuna dayanarak "{req.topic}" konusunda {req.question_count} adet çoktan seçmeli soru üret.
Ders Notu: {context}

Sadece JSON formatında yanıt ver:
{{"questions": [{{"id": "q1", "question": "...", "options": {{"A":"...","B":"...","C":"...","D":"..."}}, "correct": "A", "explanation": "..."}}]}}
"""

    start = time.time()

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        raw_text = response.content
    except Exception as e:
        print("!!! LLM HATASI (generate):", str(e))
        raise HTTPException(500, f"LLM hatası: {str(e)}")

    llm_duration.labels(operation="quiz_generate").observe(time.time() - start)

    try:
        quiz_data = _parse_json_response(raw_text)
    except json.JSONDecodeError as e:
        print("!!! JSON PARSE HATASI:", raw_text)
        raise HTTPException(500, f"LLM geçersiz JSON döndürdü: {str(e)}")

    quiz_id = str(uuid.uuid4())

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO quizzes (id, student_id, topic, questions, created_at) VALUES (%s,%s,%s,%s,NOW())",
            (quiz_id, req.student_id, req.topic, json.dumps(quiz_data["questions"])),
        )
        conn.commit()
    conn.close()

    quiz_counter.labels(topic=req.topic).inc()

    return {
        "quiz_id": quiz_id,
        "topic": req.topic,
        "questions": quiz_data["questions"]
    }


class SubmitRequest(BaseModel):
    student_id: str
    quiz_id: str
    answers: dict


@router.post("/quiz/submit")
async def submit_answers(req: SubmitRequest):

    llm = get_llm()

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT topic, questions FROM quizzes WHERE id = %s", (req.quiz_id,))
        row = cur.fetchone()

    if not row:
        raise HTTPException(404, "Quiz bulunamadı.")

    topic, questions = row[0], row[1]

    if isinstance(questions, str):
        questions = json.loads(questions)

    wrong_questions = [
        q for q in questions
        if req.answers.get(q["id"]) != q["correct"]
    ]

    correct_count = len(questions) - len(wrong_questions)
    score = round((correct_count / len(questions)) * 100)
    score_histogram.observe(score)

    analysis = None
    weak_subtopics = []

    if wrong_questions:
        context = _query_context(req.student_id, topic, n_results=3)

        wrong_summary = "\n".join([
            f"- Soru: {q['question']} | Öğrenci: {req.answers.get(q['id'], '?')} | Doğru: {q['correct']}"
            for q in wrong_questions
        ])

        prompt = f"""
Öğrenci "{topic}" konusunda şu soruları yanlış yaptı:
{wrong_summary}

İlgili ders notu: {context}

Sadece JSON:
{{"weak_subtopics": ["..."], "likely_reasons": ["..."], "recommendation": "..."}}
"""

        start = time.time()

        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            raw_text = response.content
        except Exception as e:
            print("!!! LLM HATASI (analyze):", str(e))
            raise HTTPException(500, f"LLM hatası: {str(e)}")

        llm_duration.labels(operation="answer_analyze").observe(time.time() - start)

        try:
            analysis = _parse_json_response(raw_text)
        except json.JSONDecodeError:
            print("!!! JSON PARSE HATASI (analyze):", raw_text)
            analysis = {
                "weak_subtopics": [],
                "likely_reasons": [],
                "recommendation": "Analiz yapılamadı."
            }

        weak_subtopics = analysis.get("weak_subtopics", [])

        for subtopic in weak_subtopics:
            weak_topic_counter.labels(topic=subtopic).inc()

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO quiz_results (quiz_id, student_id, score, answers, wrong_questions, analysis, completed_at) VALUES (%s,%s,%s,%s,%s,%s,NOW())",
            (
                req.quiz_id,
                req.student_id,
                score,
                json.dumps(req.answers),
                json.dumps([q["id"] for q in wrong_questions]),
                json.dumps(analysis),
            ),
        )
        conn.commit()

    conn.close()

    return {
        "score": score,
        "correct": correct_count,
        "total": len(questions),
        "wrong_count": len(wrong_questions),
        "analysis": analysis,
        "message": "Harika!" if score >= 70 else "Biraz daha çalışman gerekiyor."
    }
