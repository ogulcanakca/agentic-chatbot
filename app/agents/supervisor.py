# app/agents/supervisor.py

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from app.core.llm import get_llm
from configs.agent_config import VALID_TARGET_CATEGORIES, DEFAULT_TARGET_CATEGORY, CLASSIFICATION_PROMPT_TEMPLATE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# Sorgu sınıflandırma için kullanılan fonksiyon
def classify_query(state: Dict[str, Any]) -> Dict[str, Any]:

    logging.info("Supervisor Agent çalıştırılıyor (Sorgu Sınıflandırma)...")
    query: Optional[str] = state.get("query")
    # Başlangıçta varsayılan kategoriye ayarlayalıyoruz
    classification_decision = DEFAULT_TARGET_CATEGORY
    source_info = "Supervisor"

    # Geçerli bir sorgu bulunamadıysa kategori 'Other' olarak ayarlanacak veya
    if not query or not query.strip():
        logging.warning("Supervisor: State'de geçerli bir sorgu bulunamadı veya sorgu boş. Kategori 'Other' olarak ayarlandı.")
        classification_decision = "Other"
        source_info += " (Hata: Boş Sorgu)"
    # eğer sorgu geçerliyse sınıflandırma yapacağız
    else:
        logging.info(f"Sınıflandırılacak sorgu: '{query}'")
        try:
            # LLM'i çağırıyoruz 0.0 temperature ile. Çünkü sınıflandırma yapıyoruz sorguyu ve kesin bir kategori döndürmesini istiyoruz.
            llm = get_llm(temperature=0.0)

            # Prompt'u oluşturuyoruz
            category_list_str = ", ".join([f"'{cat}'" for cat in VALID_TARGET_CATEGORIES])
            prompt = CLASSIFICATION_PROMPT_TEMPLATE.format(
                query=query,
                category_list_str=category_list_str # Prompt içinde kategori listesini geçiyoruz
            )
            logging.debug("Sınıflandırma prompt'u LLM'e gönderiliyor...")
            # LLM'e sorguyu gönderiyoruz
            response = llm.invoke(prompt)
            llm_output = response.content.strip()
            logging.info(f"LLM sınıflandırma çıktısı (ham): '{llm_output}'")

            # LLM'in sadece kategori adını döndürdüğünden emin oluyoruz
            if llm_output in VALID_TARGET_CATEGORIES:
                classification_decision = llm_output
                logging.info(f"Sorgu başarıyla sınıflandırıldı: '{classification_decision}'")
                source_info += " (LLM Başarılı)"
            else:
                # Eğer LLM beklenenden farklı bir şey döndürürse
                # yine de çıktının içinde geçerli kategori var mı diye kontrol ediyoruz
                found_category = None
                for valid_cat in VALID_TARGET_CATEGORIES:
                    if valid_cat in llm_output:
                        found_category = valid_cat
                        logging.warning(f"LLM çıktısı '{llm_output}' tam olarak eşleşmedi ama içinde geçerli kategori '{found_category}' bulundu. Bu kategori kullanılacak.")
                        break
                if found_category:
                     classification_decision = found_category
                     source_info += " (LLM Kısmen Başarılı)"
                else:
                     # Geçerli kategori hiç bulunamazsa varsayılana dönüyor
                     logging.error(f"LLM çıktısı '{llm_output}' geçerli kategorilerle ({VALID_TARGET_CATEGORIES}) eşleşmiyor veya içinde bulunamıyor! Varsayılan kategori '{DEFAULT_TARGET_CATEGORY}' kullanılacak.")
                     classification_decision = DEFAULT_TARGET_CATEGORY
                     source_info += " (Hata: Geçersiz LLM Çıktısı)"
        # LLM çağrısı sırasında bir hata olursa varsayılan kategori dönüyoruz
        except Exception as e:
            logging.error(f"Sorgu sınıflandırması sırasında hata: {e}", exc_info=True)
            classification_decision = DEFAULT_TARGET_CATEGORY
            source_info += f" (Hata: {type(e).__name__})"

    # LangGraph state'ine 'classification' anahtarını ekleyerek döndürüyoruz
    logging.info(f"Supervisor tamamlandı. Sonuç Sınıflandırma: '{classification_decision}'")
    return {"classification": classification_decision}
