# app/agents/agentic_rag_agent.py

import logging
import sys
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List
import streamlit as st # Streamlit'i import et

# --- LangChain ve Diğer Importlar (Aynı kalıyor) ---
# ... (Chroma, Embeddings, Loaders, Splitter, PromptTemplate vb.) ...
from langchain_community.vectorstores import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
# --- Yerel Importlar (Aynı kalıyor) ---
from app.core.llm import get_llm
# AgentState import'una artık gerek yok
# from app.state import AgentState

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
from configs.app_config import (LOADER_MAPPING)
from configs.agent_config import (RAG_PROMPT_TEMPLATE)

# --- LOADER_MAPPING, RAG_PROMPT_TEMPLATE (Aynı kalıyor) ---



# Fonksiyon imzasını dict olarak değiştirebiliriz
def handle_uploaded_doc_query(state: dict) -> Dict[str, Any]:
    """
    Streamlit session state'de saklanan aktif belgeyi kullanarak sorguyu yanıtlar.
    """
    logging.info("Agentic RAG Agent çalıştırılıyor (Session State'den okuyacak)...")
    query: Optional[str] = state.get("query")

    # --- Aktif Belgeyi Session State'den Oku ---
    processed_info = st.session_state.get("processed_upload_info")
    # ------------------------------------------

    # Sorgu kontrolü
    if not query:
        logging.error("Agentic RAG: State içinde sorgu bulunamadı!")
        return {"answer": "Sorgu alınamadı.", "source": "Agentic RAG (Hata)"}

    # Aktif Belge Kontrolü
    if not processed_info or not processed_info.get("content") or not processed_info.get("filename"):
        logging.warning("Agentic RAG: Oturumda işlenmiş ve aktif bir belge bulunamadı.")
        return {"answer": "Bu soruyu yanıtlamak için lütfen önce bir belge yükleyin.", "source": "Agentic RAG (Hata: Belge Yok)"}

    # Bilgiyi session state'den al
    uploaded_file_data: bytes = processed_info["content"]
    uploaded_file_name: str = processed_info["filename"]
    source_info = f"Aktif Belge ({uploaded_file_name})" # Kaynak adını güncelle

    temp_file_path = None
    try:
        # --- Kalan adımlar (Geçici dosya, yükleme, bölme, embedding, RAG) ---
        # Bu adımlar büyük ölçüde aynı kalıyor, sadece başlangıçta
        # veriyi session state'den aldık.

        # 1. Geçici Dosya Oluşturma
        file_suffix = Path(uploaded_file_name).suffix.lower() or ".txt"
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix) as temp_file:
             temp_file.write(uploaded_file_data)
             temp_file_path = temp_file.name
             logging.info(f"Oturumdaki belge geçici olarak şuraya kaydedildi: {temp_file_path}")

        # 2. Doküman Yükleme
        loader_class = LOADER_MAPPING.get(file_suffix)
        if not loader_class:
            logging.error(f"Desteklenmeyen dosya türü: {file_suffix}")
            return {"answer": f"Üzgünüm, '{file_suffix}' uzantılı dosya türü desteklenmiyor.", "source": source_info + " (Hata)"}
        loader = loader_class(temp_file_path)
        documents = loader.load()
        logging.info(f"{len(documents)} doküman parçası yüklendi ({uploaded_file_name}).")

        # 3. Metin Bölme
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks = text_splitter.split_documents(documents)
        logging.info(f"Doküman {len(chunks)} parçaya (chunk) bölündü.")
        if not chunks:
             logging.warning("Dokümandan işlenecek metin parçası çıkarılamadı.")
             return {"answer": "Aktif dokümandan anlamlı bir içerik çıkarılamadı.", "source": source_info}

        # 4. Embedding Modeli
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            logging.error("GEMINI_API_KEY ortam değişkeni bulunamadı!")
            return {"answer": "API anahtarı yapılandırılmadığı için işlem yapılamıyor.", "source": "Agentic RAG (Hata: API Key)"}
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=gemini_api_key)

        # 5. Vektör Deposu
        logging.info("In-memory Chroma vektör deposu oluşturuluyor...")
        vectorstore = Chroma.from_documents(documents=chunks, embedding=embeddings)
        logging.info("Vektör deposu hazırlandı.")

        # 6. Retriever
        retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={'k': 5})

        # 7. RAG Zinciri ve LLM Çağrısı
        llm = get_llm(temperature=0.2)
        if not llm:
             logging.error("LLM örneği oluşturulamadı!")
             return {"answer": "Yanıt üretici motor (LLM) başlatılamadı.", "source": "Agentic RAG (Hata)"}
        prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)
        rag_chain = (
            {"context": retriever, "question": RunnablePassthrough()} | prompt | llm | StrOutputParser()
        )
        logging.info("RAG zinciri LLM ile çağrılıyor (aktif belge bağlamında)...")
        answer = rag_chain.invoke(query)
        logging.info("Yanıt LLM'den alındı.")

        # 8. Kullanılan Bağlamı Alma
        relevant_docs = retriever.get_relevant_documents(query)
        context_for_display = "\n\n---\n\n".join([doc.page_content for doc in relevant_docs])

        # 9. Sonuçları Döndürme
        return { "answer": answer, "context": context_for_display, "source": source_info }

    except Exception as e:
        logging.error(f"Agentic RAG sırasında hata (aktif belge): {e}", exc_info=True)
        return {"answer": f"Üzgünüm, aktif belge işlenirken bir hata oluştu: {type(e).__name__}", "source": source_info + " (Hata)"}

    finally:
        # 10. Geçici Dosyayı Silme
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logging.info(f"Geçici dosya silindi: {temp_file_path}")
            except Exception as e_clean:
                logging.error(f"Geçici dosya silinirken hata: {e_clean}", exc_info=True)