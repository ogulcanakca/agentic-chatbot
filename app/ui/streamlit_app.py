# app/ui/streamlit_app.py

import sys
import streamlit as st
from pathlib import Path
import logging
import time

# --- Proje Yolu ve Importlar ---
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
from app.graph import graph_app

# --- Streamlit Sayfa Konfigürasyonu ---
st.set_page_config(
    page_title="Agentic Chatbot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="auto"
)

st.title("🤖 Agentic AI Chatbot")
st.markdown("""
Resmi Gazete, güncel konular veya seyahat planlama hakkında sorularınızı yanıtlayabilirim.
**Ayrıca, aşağıdan bir doküman yükleyerek o doküman özelinde sorular sorabilirsiniz.**
""")

# --- Session State Tanımlamaları ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "processed_upload_info" not in st.session_state:
    st.session_state.processed_upload_info = None
if "new_upload_triggered" not in st.session_state:
    st.session_state.new_upload_triggered = False

# --- on_change Callback Fonksiyonu ---
def handle_file_upload():
    uploaded_file = st.session_state.get("rag_file_uploader")
    if uploaded_file is not None:
        logging.info(f"on_change: Yeni dosya algılandı - {uploaded_file.name}")
        try:
            content = uploaded_file.getvalue()
            st.session_state.processed_upload_info = {
                "filename": uploaded_file.name,
                "content": content,
                "type": uploaded_file.type
            }
            st.session_state.new_upload_triggered = True
            # Başarı mesajını burada vermek yerine ana akışta, state kontrolü ile vereceğiz.
        except Exception as e:
            logging.error(f"Dosya içeriği okunurken hata: {e}", exc_info=True)
            st.error(f"'{uploaded_file.name}' dosyası okunurken bir hata oluştu.", icon="⚠️")
            st.session_state.processed_upload_info = None
            st.session_state.new_upload_triggered = False
    else:
        # Kullanıcı widget'taki 'x' ile dosyayı temizlediğinde state'i SİLME.
        logging.info("on_change: Dosya widget'tan temizlendi. Aktif belge bağlamı korunuyor.")
        st.session_state.new_upload_triggered = False # Yeni yükleme olmadığını belirt

# --- Dosya Yükleme ve Aktif Belge Yönetimi Alanı ---
with st.container(border=True):
    st.subheader("📄 Doküman Yükle & Yönet (Agentic RAG)") # Başlık güncellendi
    st.file_uploader(
        "Analiz etmek ve soru sormak istediğiniz bir doküman seçin (PDF, TXT, DOCX vb.)",
        type=["pdf", "txt", "md", "docx"],
        key="rag_file_uploader",
        on_change=handle_file_upload
    )

    # --- Aktif Belge Bilgisini ve Temizleme Düğmesini Göster ---
    active_doc_info = st.session_state.get("processed_upload_info")
    if active_doc_info:
        col1_info, col2_clear = st.columns([4, 1]) # Bilgi ve düğme için sütunlar
        with col1_info:
            st.info(f"Aktif Belge Bağlamı: **{active_doc_info['filename']}**", icon="ℹ️")
        with col2_clear:
            # YENİ: Aktif belge bağlamını temizleme düğmesi
            if st.button("❌ Aktif Belgeyi Kaldır", key="clear_active_doc_button", help="Sadece mevcut belge bağlamını kaldırır, sohbet geçmişini silmez."):
                logging.info("Kullanıcı aktif belge bağlamını temizledi.")
                st.session_state.processed_upload_info = None
                st.session_state.new_upload_triggered = False
                st.success("Aktif belge bağlamı kaldırıldı.", icon="🗑️")
                time.sleep(1) # Mesajın görünmesi için kısa bir bekleme
                st.rerun() # Arayüzü güncelle
    # --- Bitti: Aktif Belge ve Temizleme ---

st.divider()

# --- Örnek Sorular ---
with st.container(border=False):
    st.subheader("💡 Örnek Sorular:")
    # ... (Örnek sorular aynı kalıyor) ...
    cols = st.columns(3)
    with cols[0]:
        st.markdown("- KOSGEB ve Kamu İktisadi Teşebbüsleri kapsamında yer alan teşekkül, müessese ve bağlı ortaklıkların aidat ödemeleri nasıl hesaplanacaktır?")
        st.markdown("- Cumhurbaşkanlığı Kararnamesi'nin 21'inci maddesi gereğince politika kurullarına yapılan atamalar hakkında bilgi verir misin?")
    with cols[1]:
        st.markdown("- Yarın İstanbul'dan Paris'e gitmek istiyorum, 3 gün kalacağım. Bütçem 2000 Euro.")
    with cols[2]:
        st.markdown("- Türkiye'nin güncel enflasyon oranı hakkında bilgi verir misin?")
st.divider()

# --- Sohbet Geçmişini Gösterme ---
# (Bu bölüm değişmedi, önceki kodunuzdaki gibi)
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            col1_hist, col2_hist = st.columns([4, 1])
            with col1_hist:
                st.caption(f"Kaynak: {message.get('source', 'Bilinmiyor')}")
            if message.get("response_time"):
                with col2_hist:
                    st.caption(f"⏱️ {message.get('response_time'):.2f}s")
            if message.get("pdf_path"):
                 try:
                     if Path(message["pdf_path"]).is_file():
                         with open(message["pdf_path"], "rb") as fp_hist:
                             st.download_button(
                                 label="📄 Planı İndir (PDF)", data=fp_hist,
                                 file_name=Path(message["pdf_path"]).name, mime="application/pdf",
                                 key=f"pdf_dl_hist_{message.get('source')}_{len(st.session_state.chat_history)}_{message.get('response_time')}"
                             )
                 except Exception as dl_err:
                     logging.warning(f"Geçmiş PDF indirilirken hata: {dl_err}")
            if message.get("context"):
                with st.expander("🔍 Kullanılan Bağlam (RAG)"):
                    context_key = f"ctx_hist_{message.get('source')}_{len(st.session_state.chat_history)}_{message.get('response_time')}"
                    st.text_area("", message["context"], height=150, disabled=True, key=context_key)

# --- Kullanıcı Girdisi Alma ve İşleme ---
# (Bu bölüm değişmedi, önceki kodunuzdaki gibi)
if user_input := st.chat_input("Sorunuzu buraya yazın..."):
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.spinner("Yanıt hazırlanıyor... Lütfen bekleyin..."):
        try:
            start_time = time.time()
            graph_input = {"query": user_input}
            if st.session_state.get("new_upload_triggered"):
                logging.info("Yeni yükleme işareti True. Agentic RAG'a doğrudan yönlendiriliyor.")
                graph_input["route_directly_to_agentic_rag"] = True
                st.session_state.new_upload_triggered = False
                logging.info("new_upload_triggered işareti False olarak ayarlandı.")
            else:
                logging.info("Yeni yükleme işareti False/Yok. Supervisor yönlendirecek.")

            logging.info(f"LangGraph'ı çağırıyor... Input Keys: {list(graph_input.keys())}")
            final_state = graph_app.invoke(graph_input)
            logging.info("LangGraph tamamlandı.")
            end_time = time.time()
            response_duration = end_time - start_time

            answer = final_state.get("answer", "Bir sorun oluştu, cevap alınamadı.")
            source = final_state.get("source", "Bilinmiyor")
            context = final_state.get("context")
            pdf_path = final_state.get("pdf_path")
            logging.info(f"Cevap üretildi. Kaynak: {source}. Süre: {response_duration:.2f}s.")

            assistant_response = {
                "role": "assistant", "content": answer, "source": source,
                "context": context, "pdf_path": pdf_path, "response_time": response_duration
            }
            st.session_state.chat_history.append(assistant_response)

            with st.chat_message("assistant"):
                st.markdown(answer)
                col1_resp, col2_resp = st.columns([4,1])
                with col1_resp:
                    st.caption(f"Kaynak: {source}")
                with col2_resp:
                    st.caption(f"⏱️ {response_duration:.2f}s")
                if pdf_path:
                     try:
                         if Path(pdf_path).is_file():
                             with open(pdf_path, "rb") as fp_resp:
                                 st.download_button(
                                     label="📄 Planı İndir (PDF)", data=fp_resp,
                                     file_name=Path(pdf_path).name, mime="application/pdf",
                                     key=f"pdf_dl_resp_{len(st.session_state.chat_history)}"
                                 )
                     except Exception as dl_err_resp:
                         logging.warning(f"Anlık cevap PDF indirilirken hata: {dl_err_resp}")
                         st.error("PDF indirme butonu oluşturulamadı.", icon="⚠️")
                if context:
                    with st.expander("🔍 Kullanılan Bağlam (RAG)"):
                        st.text_area("Context", context, height=200, disabled=True, key=f"ctx_resp_{len(st.session_state.chat_history)}")

        except Exception as e:
            logging.error(f"Sorgu işlenirken hata oluştu: {e}", exc_info=True)
            error_msg_for_user = f"Üzgünüm, bir hata oluştu ve isteğinizi işleyemedim.\nHata Detayı: {type(e).__name__}"
            st.session_state.chat_history.append({"role": "assistant", "content": "Üzgünüm, bir hata oluştu.", "source": "Sistem Hatası"})
            with st.chat_message("assistant"):
                st.error(error_msg_for_user)

# --- Kenar Çubuğu ---
# (Bu bölüm değişmedi, önceki kodunuzdaki gibi)
with st.sidebar:
    st.header("ℹ️ Bilgi")
    st.markdown(
        """
        Bu chatbot, **Resmi Gazete** içerikleri, **güncel olaylar/genel bilgiler**
        ve **seyahat planlama** hakkındaki sorularınızı yanıtlamak üzere tasarlanmıştır.

        - **Resmi Gazete Soruları:** İlgili belgeler taranarak cevap üretilir (RAG).
        - **Seyahat Planlama:** Detaylı planlama ve harita oluşturulur.
        - **Doküman Sorgulama (Yeni!):** Yüklediğiniz doküman içeriğiyle ilgili sorularınızı yanıtlar (Agentic RAG). Aktif bir belge varken, sorularınız öncelikle bu belge bağlamında değerlendirilir.
        - **Diğer Sorular:** Web araması veya Wikipedia kullanılarak yanıtlanır.
        """ # Bilgi metni güncellendi
    )
    st.divider()
    st.header("⚙️ Seçenekler")
    if st.button("🧹 Sohbeti Temizle", use_container_width=True):
        st.session_state.chat_history = []
        # Aktif belge bilgisini ve işareti de temizleyelim
        st.session_state.processed_upload_info = None
        st.session_state.new_upload_triggered = False
        st.success("Sohbet geçmişi ve aktif belge bilgisi temizlendi!", icon="🗑️")
        time.sleep(1)
        st.rerun() # Widget'ı sıfırlamak için

    st.divider()
    st.caption("Generative AI Bootcamp - Final Projesi")
    st.caption("Oğulcan Akca")