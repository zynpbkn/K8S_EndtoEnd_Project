from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from services.api_gateway import router as api_router
from services.quiz_service import router as quiz_router
from services.embedding_service import router as embedding_router
from services.progress_service import router as progress_router

app = FastAPI(title="AkıllıSınıf", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

Instrumentator().instrument(app).expose(app)

app.include_router(api_router, tags=["Gateway"])
app.include_router(quiz_router, tags=["Quiz"])
app.include_router(embedding_router, tags=["Embedding"])
app.include_router(progress_router, tags=["Progress"])


@app.get("/health")
async def health():
    return {"status": "ok"}
