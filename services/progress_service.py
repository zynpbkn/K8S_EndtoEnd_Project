from fastapi import APIRouter, HTTPException
from prometheus_client import Counter, Gauge
import psycopg2, psycopg2.extras, os

router = APIRouter()

progress_counter = Counter("akilli_sinif_progress_queries_total", "İlerleme sorgu sayısı")
avg_score_gauge  = Gauge("akilli_sinif_student_avg_score", "Öğrenci ortalama skoru", ["student_id"])


def get_db():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


@router.get("/progress/{student_id}")
async def get_progress(student_id: str):
    conn = get_db()
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT COUNT(*) AS total, AVG(score) AS avg, MAX(score) AS best, MIN(score) AS worst FROM quiz_results WHERE student_id = %s",
            (student_id,),
        )
        stats = cur.fetchone()

        cur.execute(
            "SELECT q.topic, AVG(r.score) AS avg_score, COUNT(*) AS attempts FROM quiz_results r JOIN quizzes q ON q.id = r.quiz_id WHERE r.student_id = %s GROUP BY q.topic ORDER BY avg_score ASC",
            (student_id,),
        )
        by_topic = cur.fetchall()

        cur.execute(
            "SELECT analysis FROM quiz_results WHERE student_id = %s AND analysis IS NOT NULL ORDER BY completed_at DESC LIMIT 5",
            (student_id,),
        )
        analyses = cur.fetchall()
    conn.close()

    if not stats["total"]:
        raise HTTPException(404, "Sonuç bulunamadı.")

    weak_topics    = [t["topic"] for t in by_topic if t["avg_score"] < 60]
    weak_subtopics = list({
        st for row in analyses if row["analysis"]
        for st in row["analysis"].get("weak_subtopics", [])
    })

    avg = float(stats["avg"] or 0)
    avg_score_gauge.labels(student_id=student_id).set(avg)
    progress_counter.inc()

    return {
        "student_id": student_id,
        "statistics": {
            "total_quizzes": stats["total"],
            "average_score": round(avg, 1),
            "best_score":    stats["best"],
            "worst_score":   stats["worst"],
        },
        "by_topic":       [dict(t) for t in by_topic],
        "weak_topics":    weak_topics,
        "weak_subtopics": weak_subtopics,
        "recommendation": (
            f"Şu konulara odaklan: {', '.join(weak_subtopics or weak_topics)}"
            if (weak_subtopics or weak_topics) else "Harika gidiyorsun! 🎉"
        ),
    }
