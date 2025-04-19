# app/tools/rag_tools.py

import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional, Any
import time

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from app.storage.database import get_or_create_collection, query_collection

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# ChromaDB koleksiyonundan, verilen sorguyla en ilgili dokümanları çeker.
def retrieve_documents(
    query: str,
    collection_name: str,
    n_results: int = 5,
    where_filter: Optional[Dict[str, Any]] = None,
    where_document_filter: Optional[Dict[str, Any]] = None,
    score_threshold: Optional[float] = None
) -> List[Dict[str, Any]]:
    
    # Sorgu metni ve koleksiyon adı boş olamaz, o yüzden kontrol ediyoruz yine de
    if not query:
        logging.warning("Boş sorgu metni ile doküman çekme işlemi yapılamaz.")
        return []
    if not collection_name:
         logging.error("Koleksiyon adı belirtilmeden doküman çekme işlemi yapılamaz.")
         return []

    # Doküman getirme işleminin süresini ölçmeye başlıyoruz
    function_start_time = time.time()
    logging.info(f"'{collection_name}' koleksiyonundan '{query}' sorgusu için {n_results} sonuç aranıyor...")
    
    # Filtreleme bilgilerini logluyoruz
    if where_filter: logging.info(f"  Metadata Filtresi: {where_filter}")
    # Doküman filtresi varsa ve metadata filtresinden farklıysa logluyoruz
    if where_document_filter: logging.info(f"  Doküman Filtresi: {where_document_filter}")
    # Skor eşiği varsa logluyoruz
    if score_threshold: logging.info(f"  Uzaklık Eşiği: < {score_threshold}")

    retrieved_docs = []
    # Koleksiyonu al veya oluştur
    collection = get_or_create_collection(collection_name)

    # Sorgu süresi için ölçüm başlatıyoruz
    query_start_time = time.time()
    # Sorgu yapıyoruz ve sonuçları alıyoruz
    results = query_collection(
        collection=collection,
        query_texts=[query],
        n_results=n_results,
        where_filter=where_filter,
        where_document_filter=where_document_filter,
        include=["metadatas", "documents", "distances"]
    )
    # Sorgu süresinin ölçümünü bitiriyoruz ve logluyoruz
    query_end_time = time.time()
    logging.info(f"Veritabanı sorgusu {query_end_time - query_start_time:.3f} saniyede tamamlandı.")

    # Her sonuç iç içe liste yapısında dönüyor
    if results and results.get('ids') and results['ids'][0]:
        # Biz tek sorgu gönderdiğimiz için hep [0] indisini kullanıyoruz
        ids = results['ids'][0]
        # Eğer sonuçlarda doküman, metadata ve uzaklık bilgileri varsa alıyoruz
        documents = results['documents'][0] if results.get('documents') else [None] * len(ids)
        metadatas = results['metadatas'][0] if results.get('metadatas') else [{}] * len(ids)
        distances = results['distances'][0] if results.get('distances') else [None] * len(ids)

        # Her bir sonuç için döngü başlatıyoruz
        for i, doc_id in enumerate(ids):
            # Listedeki i. indeksteki uzaklık değerini alıyoruz.
            # Bu değer o dokümanın sorgu vektörüne olan vektörel mesafesi.
            distance = distances[i]
            # Skor eşiği kontrolü yapıyoruz
            if score_threshold is not None and distance is not None and distance >= score_threshold:
                logging.debug(f"Doküman (ID: {doc_id}, Uzaklık: {distance:.4f}) eşik ({score_threshold}) nedeniyle atlandı.")
                continue # Eşiği geçemeyenleri atlıyoruz

            # Eşiği geçen dokümanları listeye ekliyoruz
            retrieved_docs.append({
                "id": doc_id,
                "document": documents[i] if documents else None,
                "metadata": metadatas[i] if metadatas else {},
                "distance": distance
            })

        logging.info(f"Sorgu sonucu {len(ids)} doküman bulundu, {len(retrieved_docs)} tanesi eşiği geçti (varsa) ve döndürülüyor.")
    else:
        logging.info("Veritabanı sorgusu sonuç döndürmedi.")

    # Doküman getirme işleminin süresini hesaplamayı bitiriyoruz ve logluyoruz.
    function_end_time = time.time()
    logging.info(f"retrieve_documents işlemi {function_end_time - function_start_time:.3f} saniyede tamamlandı.")
    
    # Eğer sonuç yoksa veya boşsa, boş liste döndürüyoruz
    return retrieved_docs

# Doküman listesini, LLM prompt'una eklenebilecek okunabilir bir metin bloğuna dönüştüren fonksiyonu tanımlıyoruz.
def format_context(retrieved_docs: List[Dict[str, Any]]) -> str:
    # Eğer getirilen doküman yoksa, boş string döndürüyoruz prompt için
    if not retrieved_docs:
        logging.info("Formatlanacak doküman bulunamadı, boş context döndürülüyor.")
        return ""

    # Formatlanacak dokümanları saklayacağımız listeyi tanımlıyoruz
    context_parts = []
    # Dokümanlar arasına daha belirgin bir ayırıcı koyalım
    separator = "\n\n--- Kaynak Ayracı ---\n\n"

    logging.info(f"{len(retrieved_docs)} adet doküman LLM context'i için formatlanıyor...")

    # Her bir dokümanı döngü ile formatlıyoruz
    for i, doc in enumerate(retrieved_docs):
        doc_content = doc.get('document', '').strip()
        # İçerik boşsa bu kaynağı atlıyoruz
        if not doc_content: 
            logging.warning(f"Kaynak {i+1} (ID: {doc.get('id')}) içeriği boş, formatlamada atlanıyor.")
            continue
        
        # Metadata bilgilerini alıyoruz ve
        context_part = f"Kaynak {i+1}:\n{doc_content}"
        # context_parts'a metadata bilgilerini ekliyoruz
        context_parts.append(context_part)

    # Tüm formatlanmış parçaları birleştir
    formatted_context = separator.join(context_parts)
    
    return formatted_context
