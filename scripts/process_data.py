# scripts/process_data.py

import sys
import json
import logging
from pathlib import Path
import hashlib

project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from app.utils.text_processing import split_text
from configs.script_config import DATA_SOURCES, CHUNK_SIZE, CHUNK_OVERLAP, RAW_DATA_DIR, PROCESSED_DATA_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# hashlib modülünü kullanarak benzersiz ID'ler oluşturmak için SHA-1 hash fonksiyonunu kullanıyoruz
def generate_unique_id(item_data: dict, file_stem: str, item_index: int) -> str:
    # item_data'dan başlık ve tarih bilgilerini alıyoruz
    title = item_data.get("title", "")
    date = item_data.get("date", "")
    
    # Başlık ve tarih bilgilerini birleştirip hash fonksiyonuna veriyoruz ve
    hasher = hashlib.sha1((title + date).encode('utf-8'))
    content_hash = hasher.hexdigest()[:8] # ilk 8 karakteri alıp
    return f"{file_stem}_{item_index}_{content_hash}" # benzersiz ID olarak dönüyoruz

# JSON dosyaları halinde saklanan işlenmemiş verileri liste şeklinde alıp ve metni temizleyip chunk'lara ayıran fonksiyon 
def process_json_list_file(file_path: Path) -> list[dict]:

    logging.info(f"JSON liste dosyası işleniyor: {file_path.name}")
    processed_chunks = []
    file_stem = file_path.stem # ID üretimi için dosya kökünü alıyoruz

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                # Dosyanın tamamını JSON listesi olarak okuyoruz
                data_list = json.load(f)
        
        # Eğer dosya JSON formatında değilse veya liste değilse hata veriyoruz
            except json.JSONDecodeError:
                logging.error(f"JSON dosyası okunamadı veya liste formatında değil: {file_path.name}")
                return []

        if not isinstance(data_list, list):
            logging.error(f"JSON dosyası bir liste içermiyor: {file_path.name}")
            return []

        if not data_list:
            logging.warning(f"JSON dosyası boş bir liste içeriyor: {file_path.name}")
            return []

        logging.info(f"-> Dosyada {len(data_list)} adet öğe bulundu. İşleniyor...")

        # Listedeki her bir öğe için meta verileri ve metni almak için döngümüzü başlatıyoruz
        for item_index, item_data in enumerate(data_list):
            if not isinstance(item_data, dict):
                 logging.warning(f"Öğe {item_index} bir sözlük değil, atlanıyor: {item_data}")
                 continue
            
            # Metin içeriğini alıyoruz
            text_content = item_data.get('text')
            if not text_content or not isinstance(text_content, str):
                 logging.warning(f"Öğe {item_index}: Geçersiz veya eksik 'text' alanı, atlanıyor.")
                 continue

            # Meta veriyi alıyoruz
            metadata = {k: v for k, v in item_data.items() if k != 'text'}
            # Ek olarak dosya adını da ekliyoruz
            metadata["original_source_file"] = file_path.name


            text_content = text_content.strip() # Baştaki ve sondaki boşlukları alıyoruz

            # Eğer metin içeriği boş kalırsa atlıyoruz
            if not text_content:
                 logging.warning(f"Öğe {item_index} metin içeriği temizleme sonrası boş kaldı, atlanıyor.")
                 continue

            # Metni chunk'lara ayırıyoruz
            chunks = split_text(text_content, CHUNK_SIZE, CHUNK_OVERLAP)

            # Her chunk için ID üretip ve listeye ekliyoruz
            for chunk_index, chunk_text in enumerate(chunks):
                 # Her chunk için benzersiz ID'yi oluşturuyoruz
                 chunk_id = f"{generate_unique_id(item_data, file_stem, item_index)}_{chunk_index}"
                 processed_chunks.append({
                     "id": chunk_id,
                     "text": chunk_text,
                     "metadata": metadata.copy()
                 })

        logging.info(f"-> Dosya işlendi, toplam {len(processed_chunks)} parça oluşturuldu.")
        return processed_chunks

    # 
    except IOError as e:
        logging.error(f"Dosya okunurken hata: {file_path}. Hata: {e}", exc_info=True)
        return []
    except Exception as e:
         logging.error(f"Dosya işlenirken beklenmedik hata: {file_path}. Hata: {e}", exc_info=True)
         return []

# Script'imizin main fonksiyonunu tanımlıyoruz
def main():
    logging.info("Veri işleme süreci başlatılıyor (JSON Liste Formatı)...")
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True) # Hedef ana klasör yoksa oluşturuyoruz

    # Toplam işlenen dosya ve chunk sayısını tutmak için değişkenlerimizi tanımlıyoruz
    total_files_processed = 0
    total_chunks_generated = 0

    # Tanımlı veri kaynakları üzerinde döngümüzü başlatıyoruz
    for source_name, input_filename in DATA_SOURCES.items():
        logging.info(f"=== Kaynak işleniyor: '{source_name}' ===")
        # Kaynak dosyanın RAW halinin yolu
        source_file_path = RAW_DATA_DIR / source_name / input_filename
        # Kaynak dosyanın işlenmiş halinin kaydedileceği hedef klasör yolu
        processed_source_dir = PROCESSED_DATA_DIR / source_name
        processed_source_dir.mkdir(parents=True, exist_ok=True) 

        # İşlenmiş olan çıktı dosyasının yolu 
        output_jsonl_path = processed_source_dir / f"{source_name}_processed.jsonl"

        if not source_file_path.is_file():
            logging.warning(f"Kaynak dosyası bulunamadı, atlanıyor: {source_file_path}")
            print("-" * 50)
            continue

        # JSON liste dosyasını işliyoruz ve chunk'lara ayırıyoruz
        file_chunks = process_json_list_file(source_file_path)

        # Eğer dosyadan chunk üretilemediyse atlıyoruz, üretilirse dosyaya yazıyoruz
        if file_chunks:
            # Total işlenmiş veri ve chunk sayısını güncelliyoruz
            total_files_processed += 1
            total_chunks_generated += len(file_chunks)

            # İşlenmiş veriyi JSON Lines dosyasına yazıyoruz
            try:
                with open(output_jsonl_path, 'w', encoding='utf-8') as f:
                    for chunk_data in file_chunks:
                        json.dump(chunk_data, f, ensure_ascii=False)
                        f.write('\n')
                logging.info(f"İşlenmiş veri kaydedildi: {output_jsonl_path} ({len(file_chunks)} parça)")
            except IOError as e:
                logging.error(f"İşlenmiş veri yazılamadı: {output_jsonl_path}. Hata: {e}")
        else:
            logging.warning(f"Dosyadan hiç chunk üretilemedi: {source_file_path}")

        print("-" * 50)

    logging.info("=== Veri İşleme Süreci Tamamlandı ===")
    logging.info(f"Toplam işlenen dosya sayısı: {total_files_processed}")
    logging.info(f"Toplam üretilen chunk sayısı: {total_chunks_generated}")

if __name__ == "__main__":
    # Script'i çalıştırmadan önce news_fetcher.py ve resmi_news_fetcher.py'nin çağırılıp verileri edindiğinizden emin olun
    main()