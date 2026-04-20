import os
import time
import tempfile
import chromadb
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from prometheus_client import Counter, Histogram
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader

# Güvenli Importlar
try:
    from langchain_core.documents import Document
except ImportError:
    from langchain.schema import Document

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

router = APIRouter()

# Metrikler
embedding_counter = Counter("akilli_sinif_embeddings_total", "Embedding sayısı")
chunk_histogram = Histogram("akilli_sinif_chunks", "Chunk sayısı", buckets=[1, 5, 10, 20, 50, 100])
embedding_duration = Histogram("akilli_sinif_embedding_seconds", "Embedding süresi")

# 🔑 Embedding modeli
def get_embeddings():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY bulunamadı!")
    return GoogleGenerativeAIEmbeddings(
        model="gemini-embedding-2-preview",
        task_type="RETRIEVAL_DOCUMENT",
        google_api_key=api_key
    )

# 🔌 Chroma client
def get_chroma_client():
    return chromadb.HttpClient(
        host=os.getenv("CHROMA_HOST", "chromadb"),
        port=int(os.getenv("CHROMA_PORT", 8000))
    )

@router.post("/embed")
async def embed_document(file: UploadFile = File(...), student_id: str = Form(...)):
    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 1. PDF LOAD
        loader = PyMuPDFLoader(tmp_path)
        raw_docs = loader.load()
        print("📄 RAW_DOCS:", len(raw_docs))

        # BOŞ SAYFA TEMİZLE
        valid_raw_docs = [
            doc for doc in raw_docs
            if doc.page_content and doc.page_content.strip()
        ]
        print("CLEAN RAW_DOCS:", len(valid_raw_docs))

        if not valid_raw_docs:
            raise HTTPException(400, "PDF boş veya okunamadı")

        # 2. CHUNKING
        splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
        docs = splitter.split_documents(valid_raw_docs)
        print("✂️ CHUNKS:", len(docs))

        # 3. TEMİZLE + LİSTELEME
        final_texts = []
        final_metadatas = []
        final_embeddings = []
        
        embedding_model = get_embeddings()
        start_time = time.time()

        #  4. ATOMİK EMBEDDING (TEK TEK VE GÜVENLİ)
        for i, doc in enumerate(docs):
            text = doc.page_content.strip().replace("\n", " ")
            
            # Kısa ve anlamsız metinleri ele
            if len(text) > 50:
                try:
                    # Modeli tek tek çağırarak sayı uyuşmazlığını önlüyoruz
                    vector = embedding_model.embed_query(text)
                    
                    final_embeddings.append(vector)
                    final_texts.append(text)
                    final_metadatas.append({
                        "student_id": student_id,
                        "source": file.filename,
                        "chunk_index": i
                    })
                    print(f"✅ Chunk {i+1} başarıyla vektörize edildi.")
                except Exception as e:
                    print(f"❌ Chunk {i+1} atlandı (API Hatası): {str(e)}")

        print(f"🧠 TOPLAM BAŞARILI EMBEDDING: {len(final_embeddings)}")

        if not final_embeddings:
            raise HTTPException(status_code=500, detail="Hiçbir metin parçası vektörize edilemedi.")

        chunk_histogram.observe(len(final_texts))
        embedding_duration.observe(time.time() - start_time)
        embedding_counter.inc()

        # 5. CHROMA WRITE
        client = get_chroma_client()
        collection = client.get_or_create_collection(name=f"student_{student_id}")

        # Tüm listelerin uzunlukları garanti altına alındı
        collection.add(
            documents=final_texts,
            metadatas=final_metadatas,
            embeddings=final_embeddings,
            ids=[f"{student_id}_{int(time.time())}_{i}" for i in range(len(final_embeddings))]
        )

    except Exception as e:
        print(f"!!! EMBEDDING HATASI ({file.filename}):", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Embedding işlemi başarısız: {str(e)}"
        )

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return {
        "status": "success",
        "message": f"{file.filename} başarıyla işlendi",
        "chunks": len(final_texts),
        "student_id": student_id
    }