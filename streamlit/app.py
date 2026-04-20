import streamlit as st
import requests
import json

API_URL = "http://localhost:30800"

st.set_page_config(
    page_title="AkıllıSınıf",
    page_icon="📚",
    layout="wide"
)

st.title("📚 AkıllıSınıf")
st.caption("Kişiselleştirilmiş Öğrenme Asistanı")

# Sidebar - Öğrenci ID
with st.sidebar:
    st.header("👤 Öğrenci")
    student_id = st.text_input("Öğrenci ID", value="ogrenci_1")
    st.divider()
    st.caption("API: " + API_URL)

# Sekmeler
tab1, tab2, tab3, tab4 = st.tabs([
    "📤 Ders Notu Yükle",
    "🎯 Quiz Oluştur",
    "✍️ Quiz Çöz",
    "📊 İlerleme"
])

# ─── TAB 1: Ders Notu Yükle ───────────────────────────────────────
with tab1:
    st.header("Ders Notu Yükle")
    st.caption("PDF veya TXT dosyası yükle, sistem embedding oluşturur.")

    uploaded_file = st.file_uploader(
        "Dosya seç", type=["pdf", "txt", "md"]
    )

    if uploaded_file and st.button("📤 Yükle", type="primary"):
        with st.spinner("Yükleniyor ve işleniyor..."):
            try:
                response = requests.post(
                    f"{API_URL}/api/upload",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)},
                    params={"student_id": student_id},
                )
                if response.status_code == 200:
                    st.success(f"✅ {uploaded_file.name} başarıyla yüklendi!")
                    st.json(response.json())
                else:
                    st.error(f"Hata: {response.text}")
            except Exception as e:
                st.error(f"Bağlantı hatası: {e}")

# ─── TAB 2: Quiz Oluştur ──────────────────────────────────────────
with tab2:
    st.header("Quiz Oluştur")
    st.caption("Yüklediğin ders notundan otomatik quiz üretilir.")

    col1, col2 = st.columns(2)
    with col1:
        topic = st.text_input("Konu", placeholder="örn: Osmanlı Tarihi")
    with col2:
        question_count = st.slider("Soru Sayısı", 3, 10, 5)

    if st.button("🎯 Quiz Üret", type="primary"):
        if not topic:
            st.warning("Lütfen bir konu girin.")
        else:
            with st.spinner("Quiz üretiliyor..."):
                try:
                    response = requests.post(
                        f"{API_URL}/api/quiz/generate",
                        json={
                            "student_id": student_id,
                            "topic": topic,
                            "question_count": question_count
                        }
                    )
                    if response.status_code == 200:
                        data = response.json()
                        st.success(f"✅ {len(data['questions'])} soru üretildi!")
                        st.session_state["quiz"] = data
                        st.session_state["answers"] = {}
                        st.info("✍️ 'Quiz Çöz' sekmesine geç!")
                    else:
                        st.error(f"Hata: {response.text}")
                except Exception as e:
                    st.error(f"Bağlantı hatası: {e}")

# ─── TAB 3: Quiz Çöz ─────────────────────────────────────────────
with tab3:
    st.header("Quiz Çöz")

    if "quiz" not in st.session_state:
        st.info("Önce 'Quiz Oluştur' sekmesinden quiz üret.")
    else:
        quiz = st.session_state["quiz"]
        st.subheader(f"📝 Konu: {quiz['topic']}")

        with st.form("quiz_form"):
            answers = {}
            for q in quiz["questions"]:
                st.markdown(f"**{q['id'].upper()}. {q['question']}**")
                options = [f"{k}) {v}" for k, v in q["options"].items()]
                choice = st.radio(
                    label=q["id"],
                    options=options,
                    key=f"q_{q['id']}",
                    label_visibility="collapsed"
                )
                answers[q["id"]] = choice[0]  # A, B, C veya D
                st.divider()

            submitted = st.form_submit_button("✅ Cevapları Gönder", type="primary")

        if submitted:
            with st.spinner("Değerlendiriliyor..."):
                try:
                    response = requests.post(
                        f"{API_URL}/api/quiz/submit",
                        json={
                            "student_id": student_id,
                            "quiz_id": quiz["quiz_id"],
                            "answers": answers
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        st.session_state["last_result"] = result

                        # Skor göster
                        score = result["score"]
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Skor", f"{score}/100")
                        col2.metric("Doğru", result["correct"])
                        col3.metric("Yanlış", result["wrong_count"])

                        if score >= 70:
                            st.success(f"🎉 {result['message']}")
                        else:
                            st.warning(f"📖 {result['message']}")

                        # LLM Analizi
                        if result.get("analysis"):
                            with st.expander("🔍 Detaylı Analiz"):
                                analysis = result["analysis"]
                                if analysis.get("weak_subtopics"):
                                    st.error(f"Zayıf alt konular: {', '.join(analysis['weak_subtopics'])}")
                                if analysis.get("likely_reasons"):
                                    st.warning("Muhtemel sebepler:")
                                    for r in analysis["likely_reasons"]:
                                        st.write(f"• {r}")
                                if analysis.get("recommendation"):
                                    st.info(f"💡 {analysis['recommendation']}")
                    else:
                        st.error(f"Hata: {response.text}")
                except Exception as e:
                    st.error(f"Bağlantı hatası: {e}")

# ─── TAB 4: İlerleme ─────────────────────────────────────────────
with tab4:
    st.header("İlerleme Takibi")

    if st.button("📊 İlerlemeyi Getir", type="primary"):
        with st.spinner("Yükleniyor..."):
            try:
                response = requests.get(f"{API_URL}/api/progress/{student_id}")
                if response.status_code == 200:
                    data = response.json()
                    stats = data["statistics"]

                    # Genel istatistik
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Toplam Quiz", stats["total_quizzes"])
                    col2.metric("Ortalama Skor", f"{stats['average_score']}/100")
                    col3.metric("En İyi", f"{stats['best_score']}/100")
                    col4.metric("En Düşük", f"{stats['worst_score']}/100")

                    st.divider()

                    # Konuya göre
                    if data["by_topic"]:
                        st.subheader("📈 Konulara Göre Performans")
                        for t in data["by_topic"]:
                            score = float(t["avg_score"])
                            color = "🔴" if score < 60 else "🟡" if score < 80 else "🟢"
                            st.write(f"{color} **{t['topic']}** — Ortalama: {score:.1f} | Deneme: {t['attempts']}")

                    # Öneri
                    st.divider()
                    st.info(f"💡 {data['recommendation']}")

                    if data.get("weak_subtopics"):
                        st.error(f"⚠️ Zayıf alt konular: {', '.join(data['weak_subtopics'])}")
                elif response.status_code == 404:
                    st.info("Henüz quiz sonucu yok. Önce bir quiz çöz!")
                else:
                    st.error(f"Hata: {response.text}")
            except Exception as e:
                st.error(f"Bağlantı hatası: {e}")
