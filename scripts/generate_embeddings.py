# scripts/generate_embeddings.py

import json
import logging
import sys
from pathlib import Path
import time
from typing import List, Dict, Any, Tuple, Iterator

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from app.utils.embedding import generate_embeddings, get_embedding_model
from app.storage.database import get_or_create_collection, add_data_to_collection, get_chroma_client
from configs.script_config import DATA_FOLDERS, PROCESSED_DATA_DIR, PROCESSING_BATCH_SIZE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# JSON formatındaki işlenmiş verilerimizi batch'ler halinde okuma fonksionu
def read_processed_data_batch(file_path: Path, batch_size: int) -> Iterator[Tuple[List[str], List[str], List[Dict[str, Any]]]]:

    # Batch'ler için boş listeler
    batch_ids: List[str] = []
    batch_documents: List[str] = []
    batch_metadatas: List[Dict[str, Any]] = []
    processed_line_count = 0

    # Her satırda bir adet işlenmiş veri (haber) satır satır olduğu için
    # dosyayı satır satır okuyup işliyoruz
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                processed_line_count = i + 1
                try:
                    record = json.loads(line.strip())
                    doc_id = record.get('id')
                    doc_text = record.get('text')
                    doc_metadata = record.get('metadata')

                    # Temel kontrolleri (ID, text ve metadata'nın varlığı ve türü) sağlıyoruz
                    if not doc_id or not isinstance(doc_id, (str, int)):
                        logging.warning(f"Satır {processed_line_count}: Geçersiz veya eksik 'id', atlanıyor.")
                        continue
                    if not doc_text or not isinstance(doc_text, str):
                        logging.warning(f"Satır {processed_line_count}: Geçersiz veya eksik 'text', atlanıyor.")
                        continue
                    if doc_metadata is None or not isinstance(doc_metadata, dict):
                        doc_metadata = {}

                    # ID'leri ve metinleri batch listelerine ekliyoruz
                    batch_ids.append(str(doc_id))
                    batch_documents.append(doc_text)
                    batch_metadatas.append(doc_metadata)

                    # batch_ids, batch_documents, batch_metadatas için batch dolduysa veriyi yield edip batch listesini temizliyoruz
                    # return'e nazaran yield kullanıyoruz ki bellekteki yükü azaltalım (batch boyutuna ulaşınca veriyi gönderiyoruz)
                    if batch_size is not None and batch_size > 0 and len(batch_ids) >= batch_size:
                        yield batch_ids, batch_documents, batch_metadatas
                        batch_ids, batch_documents, batch_metadatas = [], [], []

                # JSON decode hatası veya diğer beklenmedik hatalar için loglama yapıyoruz
                except json.JSONDecodeError:
                    logging.warning(f"Satır {processed_line_count}: Geçersiz JSON formatı, atlanıyor: {line.strip()}")
                    continue
                except Exception as e:
                    logging.error(f"Satır {processed_line_count} işlenirken beklenmedik hata: {e}", exc_info=True)
                    continue # Bu satırı atla, devam etmeye çalış

        # Batch'ler halinde işleme sonucu dosya sonundaki kalan PROCESSING_BATCH_SIZE'dan az olan veriyi de yield ediyoruz.
        if batch_ids:
            yield batch_ids, batch_documents, batch_metadatas

    # Dosya okuma hatası durumunda loglama yapıyoruz ve boş listeler döndürüyoruz
    except IOError as e:
        logging.error(f"İşlenmiş veri dosyası okunamadı: {file_path}. Hata: {e}")
        yield [], [], [] 
    except Exception as e:
        logging.error(f"Veri okunurken genel hata ({file_path}): {e}", exc_info=True)
        yield [], [], []

# Veri kaynağını işleyip embedding'leri üretip veritabanına ekleme fonksiyonumuzu tanımlıyoruz
def process_and_add_batch(collection, ids, documents, metadatas) -> int:

    # ID boşsa 0 döndürüp batch'yi atlıyoruz ve embeding üretmiyoruz
    if not ids:
        return 0
    
    batch_start_time = time.time()
    logging.debug(f"'{collection.name}' için {len(ids)} adetlik batch işleniyor...")

    # Embedding üretiyoruz
    embeddings = generate_embeddings(documents)

    # Eğer embedding'ler boşsa veya ID'lerle eşleşmiyorsa hata loglayıp 0 döndürüyoruz
    if not embeddings or len(embeddings) != len(ids):
        logging.error(f"Batch için embedding üretilemedi veya sayı eşleşmiyor ({len(embeddings)} vs {len(ids)}). Bu batch veritabanına eklenmeyecek.")
        return 0 

    # Veriyi ChromaDB'ye ekliyoruz
    success = add_data_to_collection(
        collection=collection,
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    batch_end_time = time.time()
    if success:
        logging.debug(f"{len(ids)} kayıtlık batch başarıyla {batch_end_time - batch_start_time:.2f} saniyede eklendi.")
        return len(ids) # Başarılı ekleme sayısını ve 
    else:
        logging.error(f"{len(ids)} kayıtlık batch veritabanına eklenirken hata oluştu.")
        return 0 # başarısız olma durumda 0 döndürüyoruz

# Script'imizin main fonksiyonunu tanımlıyoruz
def main():
    logging.info("Embedding üretme ve veritabanına yükleme script'i başlatılıyor...")
    logging.info(f"İşlenecek Kaynaklar: {DATA_FOLDERS}")
    logging.info(f"Okuma/İşleme Batch Boyutu: {PROCESSING_BATCH_SIZE if PROCESSING_BATCH_SIZE else 'Tümü Tek Seferde'}")
    script_start_time = time.time()

    # Embedding modelini ve ChromaDB client'ı yüklüyoruz
    logging.info("Gerekli bileşenler ön yükleniyor (Embedding Modeli & ChromaDB Client)...")
    get_embedding_model()
    get_chroma_client()
    logging.info("Ön yükleme tamamlandı.")

    # Total işlem sayıları için değişkenlerimizi tanımlıyoruz
    total_processed_records = 0
    total_added_to_db = 0

    # Veri kaynaklarımız üzerinde döngü başlatıyoruz
    for source_name in DATA_FOLDERS:
        logging.info(f"=== Kaynak işleniyor: '{source_name}' ===")
        source_start_time = time.time()
        processed_file = PROCESSED_DATA_DIR / source_name / f"{source_name}_processed.jsonl" # İşlenmiş veri dosyası yolumuz

        # İşlenmiş veri dosyası yoksa kaynağı atlıyoruz
        if not processed_file.is_file():
            logging.warning(f"İşlenmiş veri dosyası bulunamadı, '{source_name}' kaynağı atlanıyor: {processed_file}")
            print("-" * 50)
            continue

        # İlgili ChromaDB koleksiyonunu alıp oluşturuyoruz
        collection = get_or_create_collection(source_name)
        if not collection:
            logging.error(f"'{source_name}' için ChromaDB koleksiyonu alıp oluşturulamadı. Bu kaynak atlanıyor.")
            print("-" * 50)
            continue

        # Kaynak işleme sayıları için değişkenlerimizi tanımlıyoruz
        source_processed_count = 0
        source_added_count = 0

        # Veriyi batch'ler halinde okuyup işliyoruz
        data_generator = read_processed_data_batch(processed_file, PROCESSING_BATCH_SIZE)

        # Her batch için döngü başlatıyoruz
        for batch_ids, batch_documents, batch_metadatas in data_generator:
            if not batch_ids: # Eğer okuma sırasında hata olduysa veya dosya boşsa
                 logging.warning(f"'{source_name}' kaynağından veri okunamadı veya dosya boş.")
                 break # bu kaynağı işlemeyi durduruyoruz

            # Batch'leri işleyip veritabanına ekliyoruz
            source_processed_count += len(batch_ids)
            added_count = process_and_add_batch(collection, batch_ids, batch_documents, batch_metadatas)
            source_added_count += added_count
            logging.info(f"Kaynak '{source_name}': {source_processed_count} kayıt okundu, {source_added_count} veritabanına eklendi...")

        source_end_time = time.time()
        # Kaynak işleme sayıları toplamına ekliyoruz
        total_processed_records += source_processed_count
        total_added_to_db += source_added_count

        logging.info(f"Kaynak '{source_name}' tamamlandı.")
        logging.info(f"  Okunan kayıt sayısı: {source_processed_count}")
        logging.info(f"  Veritabanına eklenen kayıt sayısı: {source_added_count}")
        logging.info(f"  Geçen süre: {source_end_time - source_start_time:.2f} saniye.")
        logging.info(f"  '{source_name}' koleksiyonundaki güncel kayıt sayısı: {collection.count()}")
        print("-" * 50)

    script_end_time = time.time()
    logging.info("=== Tüm Kaynakların İşlenmesi Tamamlandı ===")
    logging.info(f"Toplam okunan kayıt sayısı: {total_processed_records}")
    logging.info(f"Toplam veritabanına eklenen kayıt sayısı: {total_added_to_db}")
    logging.info(f"Toplam geçen süre: {script_end_time - script_start_time:.2f} saniye.")

if __name__ == "__main__":
    # Script'i çalıştırmadan önce news_fetcher.py ve resmi_news_fetcher.py'nin çağırılıp verileri edindiğinizden ve
    # process_data.py script'inin çağırılıp edinilen verilerin işlendiğinden emin olun
    main()