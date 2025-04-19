# app/storage/database.py

import chromadb
from chromadb.utils import embedding_functions
import logging
from pathlib import Path
import sys
from typing import List, Dict, Optional, Any

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from configs.app_config import MODEL_NAME, CHROMA_DATA_PATH, create_chroma_data_path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# ChromaDB'nin bulunacağı klasörü oluşturma fonksiyonumuzu çalıştırıyoruz
create_chroma_data_path()

# ChromaDB client nesnesini basit cache mekanizmasıyla sakladığımız global değişkenimiz
client: Optional[chromadb.Client] = None

# Embedding fonksiyonunu basit cache mekanizmasıyla sakladığımız global değişkenimiz
embedding_function: Optional[embedding_functions.SentenceTransformerEmbeddingFunction] = None

# Modeli yüklemek için fonksiyonumuz
def get_embedding_function(embedding_model_name: str = MODEL_NAME) -> embedding_functions.SentenceTransformerEmbeddingFunction:
    global embedding_function
    # Eğer embedding fonksiyonu daha önce oluşturulmadıysa, yeni bir tane oluşturuyoruz
    if embedding_function is None:
        logging.info(f"ChromaDB için '{embedding_model_name}' embedding fonksiyonu oluşturuluyor...")
        embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=embedding_model_name
            )
    return embedding_function

# ChromaDB client'ı başlatmak için bir fonksiyon tanımlıyoruz
def get_chroma_client() -> chromadb.Client:
    global client
    # Eğer client daha önce oluşturulmadıysa, yeni bir tane oluşturuyoruz
    if client is None:
        logging.info(f"ChromaDB client başlatılıyor (path: {CHROMA_DATA_PATH})...")
        client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)
    return client

# ChromaDB koleksiyonunu almak veya oluşturmak için bir fonksiyon tanımlıyoruz
def get_or_create_collection(collection_name: str, embedding_model_name: str = MODEL_NAME) -> Optional[chromadb.Collection]:

    client = get_chroma_client()
    emb_func = get_embedding_function(embedding_model_name)

    logging.info(f"'{collection_name}' koleksiyonu alınıyor veya oluşturuluyor (Embedding: {embedding_model_name})...")
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=emb_func, 
        metadata={"hnsw:space": "cosine"} # Metin embeddingleri için Cosine Similarity tercih ediyoruz
    )
    logging.info(f"'{collection_name}' koleksiyonu başarıyla alındı/oluşturuldu. Kayıt sayısı: {collection.count()}")
    return collection

# ChromaDB koleksiyonuna veri eklemek için bir fonksiyon tanımlıyoruz
def add_data_to_collection(collection: chromadb.Collection,
                           ids: List[str],
                           documents: Optional[List[str]] = None,
                           embeddings: Optional[List[List[float]]] = None,
                           metadatas: Optional[List[Dict[str, Any]]] = None) -> bool:

    # Kontrol edilecek ID'lerin listesi boş olup olmadığını kontrol ediyoruz
    if not ids:
        logging.warning("Eklenecek veri için ID listesi boş.")
        return False
    num_items = len(ids)

    # Eğer hem documents hem de embeddings None ise hata veriyoruz
    if documents is None and embeddings is None:
        logging.error("Veri eklemek için 'documents' veya 'embeddings' parametresi sağlanmalıdır.")
        return False
    # Eğer hem documents hem de embeddings sağlandıysa, embedding'leri kullanmayı tercih ediyoruz
    if documents is not None and embeddings is not None:
        logging.warning("Hem 'documents' hem de 'embeddings' sağlandı. Öncelik 'embeddings'e verilecek.")

    # ID'lerin benzersiz olup olmadığını kontrol ediyoruz
    if documents is not None and len(documents) != num_items:
        logging.error(f"ID sayısı ({num_items}) ile doküman sayısı ({len(documents)}) eşleşmiyor.")
        return False
    
    # Eğer embedding'ler sağlandıysa, bunların sayısının ID'lerin sayısıyla eşleşip eşleşmediğini kontrol ediyoruz
    if embeddings is not None and len(embeddings) != num_items:
        logging.error(f"ID sayısı ({num_items}) ile embedding sayısı ({len(embeddings)}) eşleşmiyor.")
        return False
    
    # Eğer embedding'ler None ise, ChromaDB documents'ı kullanıp kendi üretir
    if metadatas is not None and len(metadatas) != num_items:
        logging.error(f"ID sayısı ({num_items}) ile metadata sayısı ({len(metadatas)}) eşleşmiyor.")
        return False
    
    # Eğer metadata None ise, boş sözlüklerden oluşan bir liste oluştur
    safe_metadatas = metadatas if metadatas is not None else [{} for _ in range(num_items)]

    # Veri ekleme işlemini gerçekleştiriyoruz
    try:
        logging.info(f"'{collection.name}' koleksiyonuna {num_items} adet kayıt ekleniyor...")
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,   
            metadatas=safe_metadatas
        )
        logging.info(f"{num_items} kayıt başarıyla eklendi. Koleksiyondaki toplam kayıt: {collection.count()}")
        return True
    except Exception as e:
        if "ID already exists" in str(e):
             logging.error("Hata: Eklemeye çalıştığınız ID'lerden bazıları koleksiyonda zaten mevcut.")
        return False

# ChromaDB koleksiyonunu sorgulamak için bir fonksiyon tanımlıyoruz
def query_collection(collection: chromadb.Collection,
                     query_texts: Optional[List[str]] = None,
                     query_embeddings: Optional[List[List[float]]] = None,
                     n_results: int = 5,
                     where_filter: Optional[Dict[str, Any]] = None,
                     where_document_filter: Optional[Dict[str, Any]] = None,
                     include: List[str] = ["metadatas", "documents", "distances"]) -> Optional[Dict[str, Any]]:

    # Sorgu metinleri ve embedding'lerin boş olup olmadığını kontrol ediyoruz
    if query_texts is None and query_embeddings is None:
        logging.error("Sorgulama için 'query_texts' veya 'query_embeddings' sağlanmalıdır.")
        return None
    
    # Eğer hem query_texts hem de query_embeddings sağlandıysa, embedding'leri kullanmayı tercih ediyoruz
    if query_texts is not None and query_embeddings is not None:
        logging.warning("Hem 'query_texts' hem de 'query_embeddings' sağlandı. 'query_texts' kullanılacak.")
        query_embeddings = None 

    results = collection.query(
        query_texts=query_texts,
        query_embeddings=query_embeddings,
        n_results=n_results,
        where=where_filter,
        where_document=where_document_filter,
        include=include
    )
    logging.info("Sorgulama tamamlandı.")
    
    # Sonuçların varlığını kontrol ediyoruz
    if results and results.get('ids'):
            # Her sorgu için bulunan sonuç sayısını logluyoruz
            for i, ids_list in enumerate(results['ids']):
                logging.debug(f"  Sorgu {i+1} için {len(ids_list)} sonuç bulundu.")
    else:
            logging.info("Sorgu için eşleşen sonuç bulunamadı.")
    return results
