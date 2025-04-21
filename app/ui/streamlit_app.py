# app/ui/streamlit_app.py

import sys
import streamlit as st
from pathlib import Path
import logging
import time

project_root = Path(__file__).resolve().parents[2]
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
st.markdown("""
Resmi Gazete, güncel konular veya seyahat planlama hakkında sorularınızı yanıtlayabilirim.
**Ayrıca, aşağıdan bir doküman yükleyerek o doküman özelinde sorular sorabilirsiniz.**
""")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "processed_upload_info" not in st.session_state:
    st.session_state.processed_upload_info = None
if "new_upload_triggered" not in st.session_state:
    st.session_state.new_upload_triggered = False

def handle_file_upload():
    uploaded_file = st.session_state.get("rag_file_uploader")
    if uploaded_file is not None:
        logging.info(f"on_change: New file detected - {uploaded_file.name}")
        try:
            content = uploaded_file.getvalue()
            st.session_state.processed_upload_info = {
                "filename": uploaded_file.name,
                "content": content,
                "type": uploaded_file.type
            }
            st.session_state.new_upload_triggered = True
        except Exception as e:
            logging.error(f"Error reading file content: {e}", exc_info=True)
            st.error(f"An error occurred while reading the file '{uploaded_file.name}'.", icon="⚠️")
            st.session_state.processed_upload_info = None
            st.session_state.new_upload_triggered = False
    else:
        logging.info("on_change: File cleared from widget. Active document context preserved.")
        st.session_state.new_upload_triggered = False 

with st.container(border=True):
    st.subheader("📄 Upload & Manage Document (Agentic RAG)") 
    st.file_uploader(
        "Select a document you want to analyze and ask questions about (PDF, TXT, DOCX etc.)",
        type=["pdf", "txt", "md", "docx"],
        key="rag_file_uploader",
        on_change=handle_file_upload
    )

    active_doc_info = st.session_state.get("processed_upload_info")
    if active_doc_info:
        col1_info, col2_clear = st.columns([4, 1]) 
        with col1_info:
            st.info(f"Active Document Context: **{active_doc_info['filename']}**", icon="ℹ️")
        with col2_clear:
            if st.button("❌ Remove Active Document", key="clear_active_doc_button", help="Only removes the current document context, does not delete chat history."):
                logging.info("User cleared active document context.")
                st.session_state.processed_upload_info = None
                st.session_state.new_upload_triggered = False
                st.success("Active document context removed.", icon="🗑️")
                time.sleep(1)
                st.rerun() 

st.divider()

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


for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            col1_hist, col2_hist = st.columns([4, 1])
            with col1_hist:
                st.caption(f"Source: {message.get('source', 'Unknown')}")
            if message.get("response_time"):
                with col2_hist:
                    st.caption(f"⏱️ {message.get('response_time'):.2f}s")
            if message.get("pdf_path"):
                 try:
                     if Path(message["pdf_path"]).is_file():
                         with open(message["pdf_path"], "rb") as fp_hist:
                             st.download_button(
                                 label="📄 Download Plan (PDF)", data=fp_hist,
                                 file_name=Path(message["pdf_path"]).name, mime="application/pdf",
                                 key=f"pdf_dl_hist_{message.get('source')}_{len(st.session_state.chat_history)}_{message.get('response_time')}"
                             )
                 except Exception as dl_err:
                     logging.warning(f"Error downloading history PDF: {dl_err}")
            if message.get("context"):
                with st.expander("🔍 Context Used (RAG)"):
                    context_key = f"ctx_hist_{message.get('source')}_{len(st.session_state.chat_history)}_{message.get('response_time')}"
                    st.text_area("", message["context"], height=150, disabled=True, key=context_key)

if user_input := st.chat_input("Type your question here..."):
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.spinner("Preparing response..."):
        try:
            start_time = time.time()

            from langchain_core.messages import HumanMessage, AIMessage
            formatted_history = []
            for msg in st.session_state.chat_history[:-1]:
                if msg["role"] == "user":
                    formatted_history.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    formatted_history.append(AIMessage(content=msg["content"]))

            graph_input = {
                "query": user_input,
                "chat_history": formatted_history 
            }
            if st.session_state.get("new_upload_triggered"):
                logging.info("New upload flag is True. Directing to Agentic RAG.")
                graph_input["route_directly_to_agentic_rag"] = True
                st.session_state.new_upload_triggered = False
                logging.info("new_upload_triggered flag set to False.")
            else:
                logging.info("New upload flag is False/None. Supervisor will route.")

            logging.info(f"Calling LangGraph... Input Keys: {list(graph_input.keys())}")
            final_state = graph_app.invoke(graph_input)
            logging.info("LangGraph completed.")
            end_time = time.time()
            response_duration = end_time - start_time

            answer = final_state.get("answer", "A problem occurred, couldn't get an answer.")
            source = final_state.get("source", "Unknown")
            context = final_state.get("context")
            pdf_path = final_state.get("pdf_path")
            logging.info(f"Answer generated. Source: {source}. Duration: {response_duration:.2f}s.")

            assistant_response = {
                "role": "assistant", "content": answer, "source": source,
                "context": context, "pdf_path": pdf_path, "response_time": response_duration
            }
            st.session_state.chat_history.append(assistant_response)

            with st.chat_message("assistant"):
                st.markdown(answer)
                col1_resp, col2_resp = st.columns([4,1])
                with col1_resp:
                    st.caption(f"Source: {source}")
                with col2_resp:
                    st.caption(f"⏱️ {response_duration:.2f}s")
                if pdf_path:
                     try:
                         if Path(pdf_path).is_file():
                             with open(pdf_path, "rb") as fp_resp:
                                 st.download_button(
                                     label="📄 Download Plan (PDF)", data=fp_resp,
                                     file_name=Path(pdf_path).name, mime="application/pdf",
                                     key=f"pdf_dl_resp_{len(st.session_state.chat_history)}"
                                 )
                     except Exception as dl_err_resp:
                         logging.warning(f"Error downloading response PDF: {dl_err_resp}")
                         st.error("Couldn't create PDF download button.", icon="⚠️")
                if context:
                    with st.expander("🔍 Context Used (RAG)"):
                        st.text_area("Context", context, height=200, disabled=True, key=f"ctx_resp_{len(st.session_state.chat_history)}")

        except Exception as e:
            logging.error(f"Error processing query: {e}", exc_info=True)
            error_msg_for_user = f"Sorry, an error occurred and I couldn't process your request.\nError Detail: {type(e).__name__}"
            st.session_state.chat_history.append({"role": "assistant", "content": "Sorry, an error occurred.", "source": "System Error"})
            with st.chat_message("assistant"):
                st.error(error_msg_for_user)

with st.sidebar:
    st.header("ℹ️ Bilgi")
    st.markdown(
        """
        Bu chatbot, **Resmi Gazete** içerikleri, **güncel olaylar/genel bilgiler**
        ve **seyahat planlama** hakkındaki sorularınızı yanıtlamak üzere tasarlanmıştır.

        - **Resmi Gazete Soruları:** İlgili belgeler taranarak cevap üretilir (RAG).
        - **Seyahat Planlama:** Detaylı planlama ve harita oluşturulur.
        - **Doküman Sorgulama :** Yüklediğiniz doküman içeriğiyle ilgili sorularınızı yanıtlar (Agentic RAG). Aktif bir belge varken, sorularınız öncelikle bu belge bağlamında değerlendirilir.
        - **Diğer Sorular:** Web araması veya Wikipedia kullanılarak yanıtlanır.
        """
    )
    st.divider()
    st.header("⚙️ Options")
    if st.button("🧹 Clear Chat", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.processed_upload_info = None
        st.session_state.new_upload_triggered = False
        st.success("Chat history and active document information cleared!", icon="🗑️")
        time.sleep(1)
        st.rerun() 

    st.divider()
    st.caption("Oğulcan")
    st.caption("AKCA")