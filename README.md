# 📚 AkıllıSınıf — Kubernetes Bootcamp Bitirme Projesi

**AkıllıSınıf**, öğrenciler için ders notlarından RAG (Retrieval-Augmented Generation) kullanarak otomatik quizler üreten, sonuçları **Gemini 2.5 Flash** ile analiz eden ve gelişim takibi yapan uçtan uca bir **Kubernetes tabanlı bir LLM** projesidir. Eğitimde fırsat eşitliği yaratmak ve öğretmenlerin öğrenci takibini saniyeler içinde yapabilmesini sağlamak amacıyla geliştirilmiştir.

## 🚀 Her Şey Helm ile Kurulur
Proje, tek bir komutla tüm bağımlılıkları (dependencies) içerecek şekilde ayağa kalkar:


```
helm install akilli-sinif ./helm/akilli-sinif
        ↓
Otomatik kurulanlar:
  ├── akilli-sinif uygulaması   (bizim chart)
  ├── PostgreSQL                (bitnami/postgresql dependency)
  └── Prometheus + Grafana      (kube-prometheus-stack dependency)
```

---

## Teknoloji Listesi

| Teknoloji | Nasıl Kuruluyor | Ne İçin |
|---|---|---|
| FastAPI (4 servis) | Bizim Helm chart | REST API |
| Gemini 2.5 Flash | Google API (dışarıdan) | Soru üretimi + analiz |
| ChromaDB | Bizim Helm chart (StatefulSet + PVC) | Vektör arama (RAG) |
| PostgreSQL | Bitnami Helm dependency | Skor ve analiz verisi |
| Prometheus | kube-prometheus-stack dependency | Metrik toplama |
| Grafana | kube-prometheus-stack dependency | Metrik görselleştirme |
| Kubernetes | Docker Desktop | Orkestrasyon |
| Helm | WSL CLI | Paket yönetimi |

---

## Kubernetes Konseptleri

| Konsept | Nerede |
|---|---|
| Deployment | 4 FastAPI servisi |
| StatefulSet | chromadb (bizim), postgresql + prometheus (dependency) |
| PVC | chromadb-data (bizim), diğerleri dependency yönetir |
| HPA | quiz-service (2-6), embedding-service (1-4) |
| Init Container | Tüm servislerde |
| ConfigMap | env config + PostgreSQL init SQL |
| Secret | Gemini API key + DB şifresi |
| NodePort | api-gateway:30800, Grafana:30300, Prometheus:30900 |
| ServiceMonitor | Prometheus metrik toplama |

---

## Kurulum

```bash
# 1. Repo ekle
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 2. Dependency indir
cd helm/akilli-sinif && helm dependency update

# 3. Namespace
kubectl create namespace akilli-sinif

# 4. Image build
docker build -t akilli-sinif/api-gateway:v1       ./services/api-gateway/
docker build -t akilli-sinif/quiz-service:v1      ./services/quiz-service/
docker build -t akilli-sinif/embedding-service:v1 ./services/embedding-service/
docker build -t akilli-sinif/progress-service:v1  ./services/progress-service/

# 5. Kur
helm install akilli-sinif ./helm/akilli-sinif \
  --namespace akilli-sinif \
  --set secret.geminiApiKey="AIza..." \
  --set secret.postgresPassword="sifre123"
```

## Erişim
```
Uygulama:   http://localhost:30800/docs
Grafana:    http://localhost:30300   (admin / admin123)
Prometheus: http://localhost:30900
streamlit : streamlit run streamlit/app.py --server.address 0.0.0.0
```
## 👩‍🏫 Geliştirici Notu
Zeynep Bakan tarafından, eğitimde yapay zeka ve modern altyapı çözümlerini birleştirmek amacıyla geliştirilmiştir. Matematik öğretmenliğinden LLM & Kubernetese'e uzanan bu yolculuğun en somut çıktısıdır. 🎓🚀
