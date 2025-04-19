# app/ui/streamlit_app.py

import sys
import streamlit as st
from pathlib import Path
import logging
import time 
import os
import re # Regular expression için re modülünü import et

# --- FPDF_FONTPATH Ayarı Başlangıcı ---
# (Bu kısım aynı kalıyor, başında olması önemli)
project_root = Path(__file__).resolve().parents[2]
font_path = project_root / "assets/fonts" 

# --- Kalan Streamlit importları ve kodları ---
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
    
# graph_app import'u ortam değişkeni ayarlandıktan SONRA olmalı
from app.graph import graph_app 

st.set_page_config(
    page_title="Agentic Chatbot",
    page_icon="🤖",
    layout="wide", 
    initial_sidebar_state="auto"
)

st.title("🤖 Agentic AI Chatbot")
# Açıklamayı güncelleyebiliriz
st.markdown("Resmi Gazete, güncel konular veya seyahat planlama hakkında sorularınızı yanıtlayabilirim.")

# Örnek sorular aynı kalabilir
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
# ÖNEMLİ NOT: Geçmiş mesajlarda harita gösterme mantığı buraya da eklenebilir,
# ancak şimdilik sadece anlık cevap için ekliyoruz.
for message in st.session_state.chat_history:
    with st.chat_message(message["role"]): 
        st.markdown(message["content"])
        # Kaynak ve süre gösterimi
        if message["role"] == "assistant" and message.get("source"):
            col1, col2 = st.columns([4, 1])
            with col1:
                 st.caption(f"Kaynak: {message.get('source', 'Bilinmiyor')}")
            if message.get("response_time"):
                 with col2:
                    st.caption(f"⏱️ {message.get('response_time'):.2f}s")
        # PDF indirme butonu (geçmiş mesajlar için) - İsteğe bağlı
        if message["role"] == "assistant" and message.get("pdf_path"):
             try:
                 # Geçmiş mesajlar için dosyanın hala var olduğunu varsayıyoruz
                 # Daha sağlam bir yapı için PDF'leri kalıcı bir yerde saklamak gerekebilir
                 if Path(message["pdf_path"]).is_file():
                     with open(message["pdf_path"], "rb") as fp:
                         st.download_button(
                             label="📄 Planı İndir (PDF)",
                             data=fp,
                             file_name=Path(message["pdf_path"]).name, 
                             mime="application/pdf",
                             key=f"pdf_dl_hist_{message['content'][:10]}_{message.get('response_time')}" # Daha benzersiz key
                         )
                 # else: st.caption("PDF dosyası artık mevcut değil.") # İsteğe bağlı
             except Exception: 
                 pass # Hata olursa butonu gösterme
                 
        # RAG bağlamı gösterimi
        if message["role"] == "assistant" and message.get("context"):
            with st.expander("Kullanılan Bağlam"):
                 st.text_area("", message["context"], height=150, disabled=True, key=f"context_{message['content'][:10]}_{message.get('response_time')}")


# Kullanıcıdan girdi alma
if user_input := st.chat_input("Sorunuzu buraya yazın..."):

    # Kullanıcı mesajını göster
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Agent yanıtını oluştur
    with st.spinner("Yanıt hazırlanıyor... Lütfen bekleyin..."):
        try:
            logging.info(f"Kullanıcı Sorgusu: '{user_input}'")
            start_time = time.time()
            graph_input = {"query": user_input}
            
            logging.info("LangGraph'ı çağırıyor...")
            final_state = graph_app.invoke(graph_input)
            logging.info("LangGraph tamamlandı.")

            end_time = time.time()
            response_duration = end_time - start_time

            answer = final_state.get("answer", "Bir sorun oluştu, cevap alınamadı.")
            source = final_state.get("source", "Bilinmiyor")
            context = final_state.get("context")
            pdf_path = final_state.get("pdf_path") 

            logging.info(f"Cevap üretildi. Kaynak: {source}. Süre: {response_duration:.2f}s. PDF: {pdf_path}")

            # Asistan cevabını geçmişe ekle
            assistant_response = {
                "role": "assistant",
                "content": answer,
                "source": source,
                "context": context,
                "pdf_path": pdf_path, 
                "response_time": response_duration
            }
            st.session_state.chat_history.append(assistant_response)

            # --- Anlık olarak yeni cevabı ekranda göster ---
            with st.chat_message("assistant"):
                # 1. Önce tüm metin cevabını göster
                st.markdown(answer) 
                
                # 2. Kaynak ve süreyi göster
                st.caption(f"Kaynak: {source} ({response_duration:.2f}s)")

                # 3. --- YENİ KISIM: Harita URL'sini Bul ve Göster ---
                # TomTom statik harita URL'sini aramak için regex deseni
                # Desen: "http(s)://api.tomtom.com/map/1/staticimage" ile başlayan ve boşluk olmayan karakterlerden oluşan URL
                map_url_pattern = r"(https?://api\.tomtom\.com/map/1/staticimage[^\s]+)"
                map_url_match = re.search(map_url_pattern, answer)
                
                if map_url_match:
                    map_url = map_url_match.group(1)
                    # URL'nin sonunda olası noktalama işaretlerini temizle (isteğe bağlı)
                    map_url = map_url.strip('.,;)!?') 
                    logging.info(f"Cevapta harita URL'si bulundu: {map_url}")
                    try:
                        # Haritayı göster
                        st.image(map_url, caption="Harita Görünümü", use_container_width=True) # 'auto' veya True deneyin
                    except Exception as img_err:
                        logging.error(f"Harita görseli yüklenirken/gösterilirken hata: {img_err}")
                        st.caption("Harita görseli yüklenemedi.") # Kullanıcıya bilgi ver
                # --- Harita Gösterme Sonu ---

                # 4. PDF indirme butonu (varsa)
                if pdf_path:
                    try:
                        with open(pdf_path, "rb") as fp:
                            st.download_button(
                                label="📄 Seyahat Planını İndir (PDF)",
                                data=fp,
                                file_name=Path(pdf_path).name, 
                                mime="application/pdf",
                                key=f"pdf_dl_{len(st.session_state.chat_history)}" 
                            )
                    except FileNotFoundError:
                        st.error("Kaydedilen PDF dosyası bulunamadı.", icon="⚠️")
                    except Exception as e:
                        st.error(f"PDF indirilirken bir hata oluştu: {e}", icon="⚠️")
                        
                # 5. RAG bağlamı (varsa)
                if context:
                    with st.expander("🔍 Kullanılan Bağlam (RAG)"):
                        st.text_area("Context", context, height=200, disabled=True, key=f"ctx_{len(st.session_state.chat_history)}")
            # --- Asistan Mesaj Bloğu Sonu ---

        except Exception as e:
            # Genel Hata Yönetimi
            logging.error(f"Sorgu işlenirken hata oluştu: {e}", exc_info=True)
            # Kullanıcıya gösterilecek hata mesajını state'e eklemeden önce logla
            error_msg_for_user = f"Üzgünüm, bir hata oluştu ve isteğinizi işleyemedim.\nHata Detayı: {type(e).__name__}"
            # Session state'e daha basit bir mesaj ekleyebiliriz
            st.session_state.chat_history.append({"role": "assistant", "content": "Üzgünüm, bir hata oluştu.", "source": "Sistem Hatası"})
            # Arayüzde detaylı hata tipini göster
            with st.chat_message("assistant"):
                st.error(error_msg_for_user)
                
# Kenar çubuğu (değişiklik yok)
with st.sidebar:
    st.header("ℹ️ Bilgi")
    st.markdown(
        """
        Bu chatbot, **Resmi Gazete** içerikleri, **güncel olaylar/genel bilgiler**
        ve **seyahat planlama** hakkındaki sorularınızı yanıtlamak üzere tasarlanmıştır.

        - **Resmi Gazete Soruları:** İlgili belgeler taranarak cevap üretilir (RAG).
        - **Seyahat Planlama:** Gideceğiniz yer, tarih, süre ve bütçe gibi bilgileri vererek detaylı bir plan (harita dahil!) oluşturabilirsiniz.
        - **Diğer Sorular:** Web araması veya Wikipedia kullanılarak yanıtlanır.
        """
    )
    st.divider()
    st.header("⚙️ Seçenekler")
    if st.button("🧹 Sohbeti Temizle", use_container_width=True):
        st.session_state.chat_history = []
        st.success("Sohbet geçmişi temizlendi!", icon="🗑️")
        time.sleep(1) 
        st.rerun()

    st.divider()
    st.caption("Generative AI Bootcamp - Final Projesi")
    st.caption("Oğulcan Akca")