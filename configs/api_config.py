# configs/api_config.py

import logging
from dotenv import load_dotenv
from pathlib import Path
import os

# Proje kök dizinini bulma
project_root = Path(__file__).resolve().parents[1] 
# .env dosyasının tam yolunu oluşturma
dotenv_path = project_root / ".env"

# Ortam değişkenlerinin zaten yüklenip yüklenmediğini takip etmek için bir bayrak
_env_loaded = False

def load_env():
    """
    .env dosyasını bulur ve içindeki ortam değişkenlerini yükler.
    Fonksiyon birden çok kez çağrılsa bile yükleme işlemini sadece bir kez yapar.
    """
    global _env_loaded
    if _env_loaded:
        # logging.debug("Ortam değişkenleri zaten yüklendi.")
        return # Zaten yüklendiyse tekrar yükleme

    if dotenv_path.is_file():
        # override=True: Eğer sistemde aynı isimde değişken varsa .env'deki ezer.
        load_dotenv(dotenv_path=dotenv_path, override=True) 
        logging.info(f".env dosyasındaki ortam değişkenleri yüklendi: {dotenv_path}")
        _env_loaded = True
    else:
        # .env dosyası yoksa bile sistem genelindeki değişkenleri yüklemeyi dene
        load_dotenv(override=True) 
        logging.warning(f".env dosyası bulunamadı: {dotenv_path}. Sistem geneli değişkenler veya önceden yüklenmiş olanlar kullanılacak.")
        # .env olmasa bile yüklendi sayıyoruz ki tekrar denemesin.
        _env_loaded = True 

    # Bu fonksiyon artık bir değer döndürmüyor.

# --- ÖNEMLİ ---
# Bu modül import edildiğinde load_env() fonksiyonunun otomatik olarak çağrılmasını sağla.
# Böylece herhangi bir modül "from configs.api_config import load_env" yapsa bile,
# yükleme işlemi (eğer yapılmadıysa) gerçekleşmiş olur.
load_env() 
# --- ---