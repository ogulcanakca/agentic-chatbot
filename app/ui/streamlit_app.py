# app/ui/streamlit_app.py

import sys
import streamlit as st
from pathlib import Path
import logging
import time
import os
import re
import io

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

# --- Session State Tanımlamaları (Aynı kalıyor) ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "processed_upload_info" not in st.session_state:
    st.session_state.processed_upload_info = None
if "new_upload_triggered" not in st.session_state:
    st.session_state.new_upload_triggered = False

# --- on_change Callback Fonksiyonu (Güncellendi) ---
def handle_file_upload():
    uploaded_file = st.session_state.get("rag_file_uploader")
    if uploaded_file is not None:
        # Yeni dosya seçildiğinde eskisi varsa üzerine yazılır
        logging.info(f"on_change: Yeni dosya algılandı - {uploaded_file.name}")
        try:
            content = uploaded_file.getvalue()
            st.session_state.processed_upload_info = { # Önceki bilgiyi siler ve yenisini yazar
                "filename": uploaded_file.name,
                "content": content,
                "type": uploaded_file.type
            }
            st.session_state.new_upload_triggered = True # İlk sorgu için işareti ayarla
        except Exception as e:
            logging.error(f"Dosya içeriği okunurken hata: {e}", exc_info=True)
            st.error(f"'{uploaded_file.name}' dosyası okunurken bir hata oluştu.", icon="⚠️")
            # Hata durumunda state'i temizleyelim
            st.session_state.processed_upload_info = None
            st.session_state.new_upload_triggered = False
    else:
        # Dosya widget'tan temizlendiğinde (kullanıcı X'e bastı)
        # ÖNEMLİ: processed_upload_info'yu burada temizlemiyoruz!
        # Kullanıcının aynı belge hakkında soru sormaya devam edebilmesi için
        # son yüklenen belge bilgisini session'da tutuyoruz.
        logging.info("on_change: Dosya widget'tan temizlendi. Aktif belge bağlamı korunuyor.")
        # Sadece yeni yükleme işaretini sıfırlayalım (artık yeni değil)
        st.session_state.new_upload_triggered = False

# --- Dosya Yükleme Alanı (Aktif belge gösterimi eklendi) ---
with st.container(border=True):
    st.subheader("📄 Doküman Yükle (Agentic RAG için)")
    st.file_uploader(
        "Analiz etmek ve soru sormak istediğiniz bir doküman seçin (PDF, TXT, DOCX vb.)",
        type=["pdf", "txt", "md", "docx"],
        key="rag_file_uploader",
        on_change=handle_file_upload
    )
    # --- Aktif Belge Bilgisini Göster ---
    active_doc_info = st.session_state.get("processed_upload_info")
    if active_doc_info:
        st.info(f"Aktif Belge Bağlamı: **{active_doc_info['filename']}** (Bu belgeyle ilgili sorular sorulabilir)", icon="ℹ️")
    # --- Bitti: Aktif Belge Bilgisi ---

st.divider()

# --- Örnek Sorular ---
with st.container(border=False):
    st.subheader("💡 Örnek Sorular:")
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
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Mevcut Kaynak, süre, PDF indirme, Context gösterimi korunuyor
        if message["role"] == "assistant":
            col1_hist, col2_hist = st.columns([4, 1])
            with col1_hist:
                st.caption(f"Kaynak: {message.get('source', 'Bilinmiyor')}")
            if message.get("response_time"):
                with col2_hist:
                    st.caption(f"⏱️ {message.get('response_time'):.2f}s")

            # PDF indirme butonu (geçmiş mesajlar için)
            if message.get("pdf_path"):
                 try:
                     # Dosyanın hala var olduğunu varsayıyoruz
                     if Path(message["pdf_path"]).is_file():
                         with open(message["pdf_path"], "rb") as fp_hist:
                             st.download_button(
                                 label="📄 Planı İndir (PDF)",
                                 data=fp_hist,
                                 file_name=Path(message["pdf_path"]).name,
                                 mime="application/pdf",
                                 key=f"pdf_dl_hist_{message.get('source')}_{len(st.session_state.chat_history)}_{message.get('response_time')}" # Daha unique key
                             )
                 except Exception as dl_err:
                     logging.warning(f"Geçmiş PDF indirilirken hata: {dl_err}")
                     pass # Hata olursa butonu gösterme

            # RAG bağlamı gösterimi
            if message.get("context"):
                with st.expander("🔍 Kullanılan Bağlam (RAG)"):
                    # Key'i daha unique yapalım
                    context_key = f"ctx_hist_{message.get('source')}_{len(st.session_state.chat_history)}_{message.get('response_time')}"
                    st.text_area("", message["context"], height=150, disabled=True, key=context_key)


if user_input := st.chat_input("Sorunuzu buraya yazın..."):

    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.spinner("Yanıt hazırlanıyor... Lütfen bekleyin..."):
        try:
            start_time = time.time()
            # Temel input sadece sorgu
            graph_input = {"query": user_input}

            # Yeni yükleme işareti varsa, doğrudan yönlendirme için işaret ekle
            if st.session_state.get("new_upload_triggered"):
                logging.info("Yeni yükleme işareti True. Agentic RAG'a doğrudan yönlendiriliyor.")
                graph_input["route_directly_to_agentic_rag"] = True
                # İşareti sıfırla ki sadece bu ilk sorgu için kullanılsın
                st.session_state.new_upload_triggered = False
                logging.info("new_upload_triggered işareti False olarak ayarlandı.")
                # ARTIK DOSYA BİLGİSİNİ BURADA GÖNDERMİYORUZ!
            else:
                logging.info("Yeni yükleme işareti False/Yok. Supervisor yönlendirecek.")

            # --- LangGraph'ı Çağırma ---
            # Agentic RAG agent'ı artık dosya bilgisini session state'den alacak
            logging.info(f"LangGraph'ı çağırıyor... Input Keys: {list(graph_input.keys())}")
            final_state = graph_app.invoke(graph_input)
            logging.info("LangGraph tamamlandı.")

            end_time = time.time()
            response_duration = end_time - start_time

            # --- Yanıtı Alma ---
            answer = final_state.get("answer", "Bir sorun oluştu, cevap alınamadı.")
            source = final_state.get("source", "Bilinmiyor")
            context = final_state.get("context")
            pdf_path = final_state.get("pdf_path") # Travel agent'dan gelebilir

            logging.info(f"Cevap üretildi. Kaynak: {source}. Süre: {response_duration:.2f}s.")

            # --- Yanıtı Geçmişe Ekle ---
            assistant_response = {
                "role": "assistant", "content": answer, "source": source,
                "context": context, "pdf_path": pdf_path, "response_time": response_duration
            }
            st.session_state.chat_history.append(assistant_response)

            # --- Asistan Cevabını Anlık Gösterme ---
            with st.chat_message("assistant"):
                st.markdown(answer)
                col1_resp, col2_resp = st.columns([4,1])
                with col1_resp:
                    st.caption(f"Kaynak: {source}")
                with col2_resp:
                    st.caption(f"⏱️ {response_duration:.2f}s")

                # Anlık cevapta PDF indirme butonu (varsa)
                if pdf_path:
                     try:
                         if Path(pdf_path).is_file():
                             with open(pdf_path, "rb") as fp_resp:
                                 st.download_button(
                                     label="📄 Planı İndir (PDF)", # Veya daha genel "Dosyayı İndir"
                                     data=fp_resp,
                                     file_name=Path(pdf_path).name,
                                     mime="application/pdf", # Veya dosya türüne göre dinamik
                                     key=f"pdf_dl_resp_{len(st.session_state.chat_history)}"
                                 )
                     except Exception as dl_err_resp:
                         logging.warning(f"Anlık cevap PDF indirilirken hata: {dl_err_resp}")
                         st.error("PDF indirme butonu oluşturulamadı.", icon="⚠️")


                # Anlık cevapta RAG bağlamı (varsa)
                if context:
                    with st.expander("🔍 Kullanılan Bağlam (RAG)"):
                        st.text_area("Context", context, height=200, disabled=True, key=f"ctx_resp_{len(st.session_state.chat_history)}")

        except Exception as e:
            # Genel Hata Yönetimi
            logging.error(f"Sorgu işlenirken hata oluştu: {e}", exc_info=True)
            error_msg_for_user = f"Üzgünüm, bir hata oluştu ve isteğinizi işleyemedim.\nHata Detayı: {type(e).__name__}"
            st.session_state.chat_history.append({"role": "assistant", "content": "Üzgünüm, bir hata oluştu.", "source": "Sistem Hatası"})
            with st.chat_message("assistant"):
                st.error(error_msg_for_user)

# --- Kenar Çubuğu ---
with st.sidebar:
    st.header("ℹ️ Bilgi")
    st.markdown(
        """
        Bu chatbot, **Resmi Gazete** içerikleri, **güncel olaylar/genel bilgiler**
        ve **seyahat planlama** hakkındaki sorularınızı yanıtlamak üzere tasarlanmıştır.

        - **Resmi Gazete Soruları:** İlgili belgeler taranarak cevap üretilir (RAG).
        - **Seyahat Planlama:** Detaylı planlama ve harita oluşturulur.
        - **Doküman Sorgulama (Yeni!):** Yüklediğiniz doküman içeriğiyle ilgili sorularınızı yanıtlar (Agentic RAG).
        - **Diğer Sorular:** Web araması veya Wikipedia kullanılarak yanıtlanır.
        """
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
        st.rerun()

    st.divider()
    st.caption("Generative AI Bootcamp - Final Projesi")
    st.caption("Oğulcan Akca")