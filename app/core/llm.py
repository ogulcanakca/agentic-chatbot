# app/core/llm.py

import os
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Optional, Dict, Tuple, Any
from pathlib import Path
import sys

# Proje kök dizinini sys.path'e ekleme
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

# configs.api_config'i import etmek yeterli, içindeki kod load_env()'i çalıştıracak.
try:
    from configs import api_config 
except ImportError:
     logging.error("configs.api_config modülü bulunamadı! Ortam değişkenleri yüklenemeyebilir.")


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

llm_instances: Dict[Tuple, ChatGoogleGenerativeAI] = {}

def get_llm(
    model_name: str = "gemini-1.5-flash-latest", 
    temperature: float = 0.5, 
    max_output_tokens: Optional[int] = 2048,
    top_p: Optional[float] = None, 
    top_k: Optional[int] = None, 
    **kwargs: Any
) -> Optional[ChatGoogleGenerativeAI]:

    # GEMINI_API_KEY'i fonksiyon içinde os.getenv ile al
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        logging.error("Ortam değişkeni 'GEMINI_API_KEY' bulunamadı veya boş!")
        # İsteğe bağlı: Yüklemeyi tekrar tetiklemeyi deneyebiliriz ama api_config import edildiğinde zaten denenmiş olmalı.
        # api_config.load_env() 
        # gemini_api_key = os.getenv("GEMINI_API_KEY")
        # if not gemini_api_key: # Hala yoksa çık
        return None 

    cache_key = (
        model_name, temperature, max_output_tokens, top_p, top_k,
        tuple(sorted(kwargs.items()))
    )

    if cache_key in llm_instances:
        logging.debug(f"Önbellekten LLM örneği döndürülüyor (Ayarlar: {cache_key})")
        return llm_instances[cache_key]

    logging.info(f"Yeni LLM örneği oluşturuluyor: Model={model_name}, Temp={temperature}...")

    try:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=gemini_api_key, # os.getenv ile alınan değeri kullan
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            top_p=top_p,
            top_k=top_k,
            **kwargs
        )
        llm_instances[cache_key] = llm
        logging.info("LLM örneği başarıyla oluşturuldu ve önbelleğe alındı.")
        return llm
    except Exception as e:
        logging.error(f"LLM örneği oluşturulurken hata oluştu: {e}", exc_info=True)
        return None