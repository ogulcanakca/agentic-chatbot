# app/utils/embedding.py

import logging
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import torch
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from configs.app_config import MODEL_NAME

# Model nesnesini basit cache mekanizmasıyla sakladığımız global değişkenimiz
model: Optional[SentenceTransformer] = None

# Modeli yüklemek için bir fonksiyon tanımlıyoruz
def get_embedding_model() -> SentenceTransformer:

    global model
    if model is None:
        logging.info(f"'{MODEL_NAME}' modeli yükleniyor...")
        
        # GPU varsa kullanıyoruz, yoksa CPU'dan devam ediyoruz. 
        # CPU'da çalıştım süreç boyunca, ona rağmen hızlı çalışıyor sistem
        device = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
        logging.info(f"Kullanılacak cihaz: {device}")

        # Modeli yüklüyoruz
        model = SentenceTransformer(MODEL_NAME, device=device)

        logging.info(f"'{MODEL_NAME}' modeli başarıyla yüklendi ({device}).")
        
    return model

# Embedding üretimi için bir fonksiyon tanımlıyoruz
def generate_embeddings(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    if not texts:
        logging.warning("Embedding üretmek için boş metin listesi alındı.")
        return []

    try:
        model = get_embedding_model()
        logging.info(f"{len(texts)} adet metin için embedding üretiliyor (batch size: {batch_size})...")

        # Modeli kullanarak embedding'leri üretiyoruz
        embeddings_np = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True
        )
        logging.info("Embedding üretimi tamamlandı.")

        # JSON'da saklama ve kullanımı için NumPy array'lerini listeye çeviriyoruz
        embeddings_list = embeddings_np.tolist()
        return embeddings_list
    
     # Hata durumunda boş liste döndürüyoruz
    except Exception as e:
        logging.error(f"Embedding üretimi sırasında hata oluştu: {e}", exc_info=True)
        return []
