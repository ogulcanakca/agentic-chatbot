# app/ui/streamlit_app.py

import sys
import streamlit as st
from pathlib import Path
import logging
import time 
import os

# --- FPDF_FONTPATH Ayarı Başlangıcı ---
project_root = Path(__file__).resolve().parents[2]
font_path = project_root / "assets/fonts" 
# Ortam değişkenini ayarla (eğer zaten ayarlı değilse)
if "FPDF_FONTPATH" not in os.environ:
    os.environ["FPDF_FONTPATH"] = str(font_path.resolve())
    logging.info(f"FPDF_FONTPATH ortam değişkeni ayarlandı: {os.environ['FPDF_FONTPATH']}")
elif not str(font_path.resolve()) in os.environ["FPDF_FONTPATH"]:
    # Eğer değişken varsa ama bizim yolumuzu içermiyorsa, ekleyelim (yol ayırıcı platforma göre değişir)
    sep = os.pathsep # Windows için ';', Linux/Mac için ':'
    os.environ["FPDF_FONTPATH"] += sep + str(font_path.resolve())
    logging.info(f"FPDF_FONTPATH ortam değişkeni güncellendi: {os.environ['FPDF_FONTPATH']}")
else:
     logging.info(f"FPDF_FONTPATH zaten ayarlı ve doğru yolu içeriyor: {os.environ['FPDF_FONTPATH']}")
# --- FPDF_FONTPATH Ayarı Sonu ---


# --- Kalan Streamlit importları ve kodları ---
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
    
from app.graph import graph_app


st.set_page_config(
    page_title="Agentic Chatbot",
    page_icon="🤖",
    layout="wide", 
    initial_sidebar_state="auto"
)

st.title("🤖 Agentic AI Chatbot")
st.markdown("Resmi Gazete veya güncel konular hakkında sorularınızı yanıtlayabilirim.")

with st.container(border=True):
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

# Streamlit'in Session State özelliğiyle sohbet geçmişini saklıyoruz
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Geçmiş mesajları ekrana yazdır
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]): # Kullanıcı veya asistan rolüne göre ikon ayarlar
        st.markdown(message["content"])
        # Eğer mesaj asistandan geldiyse ve kaynak bilgisi varsa onu da gösteriyoruz
        if message["role"] == "assistant" and message.get("source"):
            col1, col2 = st.columns([4, 1])
            with col1:
                 st.caption(f"Kaynak: {message.get('source', 'Bilinmiyor')}")
            if message.get("response_time"):
                 with col2:
                    st.caption(f"⏱️ {message.get('response_time'):.2f}s")
        # RAG bağlamının arayüzde geçmiş mesajlar için gösterilmeye devam etmesi amacıyla ekliyoruz
        if message["role"] == "assistant" and message.get("context"):
            with st.expander("Kullanılan Bağlam"):
                 st.text_area("", message["context"], height=150, disabled=True, key=f"context_{message['content'][:10]}")

# UI'da kullanıcıdan girdi almak için chat_input kullanıyoruz
if user_input := st.chat_input("Sorunuzu buraya yazın..."):

    # Kullanıcı mesajını geçmişe ekleyip ekranda gösteriyoruz
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Yanıtın LangGraph agent sistemiyle oluşturulmak üzere gerekli işlemleri yapıyoruz
    with st.spinner("Yanıt hazırlanıyor... Lütfen bekleyin..."):
        try:
            logging.info(f"Kullanıcı Sorgusu: '{user_input}'")
            # Süre ölçümü başlatıyoruz
            start_time = time.time()

            # Graph'ı çalıştırmak için başlangıç state'i oluşturuyoruz
            graph_input = {"query": user_input}

            # LangGraph uygulamasını çağırıyoruz
            logging.info("LangGraph'ı çağırıyor...")
            final_state = graph_app.invoke(graph_input)
            logging.info("LangGraph tamamlandı.")

            # Süre ölçümü bitiriyoruz
            end_time = time.time()
            response_duration = end_time - start_time

            # Graph'tan dönen sonuçları (answer, source, context) alıyoruz
            answer = final_state.get("answer", "Bir sorun oluştu, cevap alınamadı.")
            source = final_state.get("source", "Bilinmiyor")
            context = final_state.get("context")
            pdf_path = final_state.get("pdf_path") # PDF yolunu al
            response_duration = end_time - start_time # Süre hesaplaması zaten var

            logging.info(f"Cevap üretildi. Kaynak: {source}. Süre: {response_duration:.2f}s. PDF: {pdf_path}")

            # Asistan cevabını geçmişe ekle (pdf_path ile)
            assistant_response = {
                "role": "assistant",
                "content": answer,
                "source": source,
                "context": context,
                "pdf_path": pdf_path, # PDF yolunu geçmişe ekle
                "response_time": response_duration
            }
            st.session_state.chat_history.append(assistant_response)

            # Anlık olarak yeni cevabı ekranda göster
            with st.chat_message("assistant"):
                st.markdown(answer)
                st.caption(f"Kaynak: {source} ({response_duration:.2f}s)")
                # Eğer PDF varsa indirme butonu göster
                if pdf_path:
                    try:
                        with open(pdf_path, "rb") as fp:
                            st.download_button(
                                label="📄 Seyahat Planını İndir (PDF)",
                                data=fp,
                                file_name=Path(pdf_path).name, # Dosya adını path'ten al
                                mime="application/pdf",
                                key=f"pdf_dl_{len(st.session_state.chat_history)}" # Benzersiz key
                            )
                    except FileNotFoundError:
                        st.error("Kaydedilen PDF dosyası bulunamadı.", icon="⚠️")
                    except Exception as e:
                        st.error(f"PDF indirilirken bir hata oluştu: {e}", icon="⚠️")
                # Bağlamı göster (RAG için)
                if context:
                    with st.expander("🔍 Kullanılan Bağlam (RAG)"):
                        st.text_area("Context", context, height=200, disabled=True, key=f"ctx_{len(st.session_state.chat_history)}")

        except Exception as e:
            logging.error(f"Sorgu işlenirken hata oluştu: {e}", exc_info=True)
            error_msg = f"Üzgünüm, bir hata oluştu ve isteğinizi işleyemedim.\nHata: {type(e).__name__}"
            st.session_state.chat_history.append({"role": "assistant", "content": error_msg, "source": "Sistem Hatası"})
            with st.chat_message("assistant"):
                st.error(error_msg)
                
# Kenar çubuğu için bilgi ve seçenekler ekliyoruz
with st.sidebar:
    st.header("ℹ️ Bilgi")
    st.markdown(
        """
        Bu chatbot, **Resmi Gazete** içerikleri ve **güncel olaylar/genel bilgiler**
        hakkındaki sorularınızı yanıtlamak üzere tasarlanmıştır.

        - **Resmi Gazete Soruları:** İlgili belgeler taranarak cevap üretilir (RAG).
        - **Seyahat Planlama:** Gideceğiniz yer, tarih, süre ve bütçe gibi bilgileri vererek detaylı bir plan oluşturabilirsiniz.
        - **Diğer Sorular:** Web araması veya Wikipedia kullanılarak yanıtlanır.
        """
    )
    st.divider()
    st.header("⚙️ Seçenekler")
    # Sohbeti temizleme butonu için bir seçenek ekliyoruz
    if st.button("🧹 Sohbeti Temizle", use_container_width=True):
        st.session_state.chat_history = []
        st.success("Sohbet geçmişi temizlendi!", icon="🗑️")
        time.sleep(1) 
        # Sayfayı yeniden yükleyerek temizliği gösteriyoruz
        st.rerun()

    st.divider()
    st.caption("Generative AI Bootcamp - Final Projesi")
    st.caption("Oğulcan Akca")
