from fastapi import APIRouter, UploadFile, File, HTTPException
from prometheus_client import Counter
from pydantic import BaseModel
import httpx, os

router = APIRouter()

upload_counter   = Counter("akilli_sinif_uploads_total", "Yüklenen dosya sayısı")
quiz_req_counter = Counter("akilli_sinif_quiz_requests_total", "Quiz istek sayısı")

#QUIZ_URL      = "http://quiz-service.akilli-sinif.svc.cluster.local:8001"
#EMBEDDING_URL = "http://embedding-service.akilli-sinif.svc.cluster.local:8002"
#PROGRESS_URL  = "http://progress-service.akilli-sinif.svc.cluster.local:8003)"

QUIZ_URL = os.getenv(
    "QUIZ_URL", 
    "http://quiz-service.akilli-sinif.svc.cluster.local:8000"
)
EMBEDDING_URL = os.getenv(
    "EMBEDDING_URL", 
    "http://embedding-service.akilli-sinif.svc.cluster.local:8002"
)
PROGRESS_URL = os.getenv(
    "PROGRESS_URL", 
    "http://progress-service.akilli-sinif.svc.cluster.local:8003"
)


@router.post("/api/upload")
async def upload_document(file: UploadFile = File(...), student_id: str = ""):
    if not file.filename.endswith((".pdf", ".txt", ".md")):
        raise HTTPException(400, "Sadece PDF, TXT veya MD yüklenebilir.")
    
    content = await file.read()
    
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            # Burası Adım 1'den Adım 2'ye geçiş noktası
            r = await client.post(
                f"{EMBEDDING_URL}/embed", 
                files={"file": (file.filename, content, file.content_type)},
                data={"student_id": student_id},
            )
            # Eğer karşı servis (Embedding) 404 veya 500 dönerse burada yakalarız
            r.raise_for_status()
            
        except httpx.HTTPStatusError as e:
            # Embedding servisi bir hata kodu döndüyse (Örn: Google model hatası)
            print(f"!!! ARKA SERVIS HATASI: {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Embedding servisi hata verdi: {e.response.text}")
            
        except Exception as e:
            # Hiç bağlanamıyorsa (Adres yanlışsa veya servis kapalıysa)
            print(f"!!! BAGLANTI HATASI: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Embedding servisine ulaşılamadı: {str(e)}")

    upload_counter.inc()
    return {"message": "Dosya başarıyla yüklendi.", "filename": file.filename}


class QuizRequest(BaseModel):
    student_id: str
    topic: str
    question_count: int = 5


@router.post("/api/quiz/generate")
async def generate_quiz(req: QuizRequest):
    quiz_req_counter.inc()
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{QUIZ_URL}/quiz/generate", json=req.model_dump())
        r.raise_for_status()
    return r.json()


class AnswerRequest(BaseModel):
    student_id: str
    quiz_id: str
    answers: dict


@router.post("/api/quiz/submit")
async def submit_answers(req: AnswerRequest):
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{QUIZ_URL}/quiz/submit", json=req.model_dump())
        r.raise_for_status()
    return r.json()


@router.get("/api/progress/{student_id}")
async def get_progress(student_id: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{PROGRESS_URL}/progress/{student_id}")
        r.raise_for_status()
    return r.json()
