# app/agents/resmi_gazete_agent.py

import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from app.tools.rag_tools import retrieve_documents, format_context
from app.core.llm import get_llm

from configs.agent_config import RESMI_GAZETE_COLLECTION, NUM_DOCUMENTS_TO_RETRIEVE, PROMPT_TEMPLATE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# İlgili dokümanlar kullanılarak cevap üretmek için kullanılan fonksiyonumuz
def generate_resmi_gazete_answer(state: Dict[str, Any]) -> Dict[str, Any]:

    logging.info("Resmi Gazete Agent çalıştırılıyor...")
    query: Optional[str] = state.get("query")
    final_answer: Optional[str] = None
    retrieved_context: Optional[str] = None
    source_info = f"Resmi Gazete (Koleksiyon: {RESMI_GAZETE_COLLECTION})" # Kaynağı detaylı belirtiyoruz

    # Sorguyu kontrol ediyoruz var mı yok mu diye
    if not query:
        logging.error("Resmi Gazete Agent: State içinde geçerli bir 'query' bulunamadı.")
        final_answer = "Anlaşılamayan veya eksik bir sorgu aldım. Lütfen sorunuzu tekrar iletin."
        source_info += " (Hata: Eksik Sorgu)"
        return {"answer": final_answer, "context": None, "source": source_info}

    logging.info(f"İşlenecek sorgu: '{query}'")

    # İlgili dokümanları çekiyoruz
    logging.debug(f"'{RESMI_GAZETE_COLLECTION}' koleksiyonundan dokümanlar çekiliyor...")
    try:
        retrieved_docs = retrieve_documents(
            query=query,
            collection_name=RESMI_GAZETE_COLLECTION,
            n_results=NUM_DOCUMENTS_TO_RETRIEVE
        )
    except Exception as e:
        logging.error(f"Doküman çekme sırasında hata oluştu: {e}", exc_info=True)
        final_answer = "Resmi Gazete belgelerine erişirken bir sorun oluştu."
        source_info += " (Hata: Doküman Çekme)"
        return {"answer": final_answer, "context": None, "source": source_info}

    # Dokümanlar, ilgili belgelerde bulunamadıysa
    if not retrieved_docs:
        logging.warning("Sorgu için ilgili Resmi Gazete dokümanı bulunamadı.")
        final_answer = f"'{query}' sorgunuzla doğrudan ilgili bir Resmi Gazete belgesi bulamadım. Farklı anahtar kelimelerle tekrar deneyebilirsiniz."
        source_info += " (Sonuç Bulunamadı)"
        retrieved_context = None
    # veya formatlanmadıysa LLM'e boş context göndermemek için burada cevap oluşturuyoruz
    else:
        logging.info(f"{len(retrieved_docs)} adet ilgili doküman bulundu.")
        try:
            retrieved_context = format_context(retrieved_docs)
            if not retrieved_context: # Formatlama sonucu boş string dönerse (örn. içerik yoksa)
                 logging.warning("Dokümanlar bulundu ancak formatlanmış context boş.")
                 final_answer = "İlgili belgeler bulundu ancak içerikleri işlenemedi veya boştu."
                 source_info += " (Hata: Boş Context)"
                 retrieved_context = "Formatlanmış context boş."
            else:
                 # Context başarıyla formatlandı, LLM'e geçebiliriz
                 pass
        except Exception as e:
            logging.error(f"Context formatlama sırasında hata oluştu: {e}", exc_info=True)
            final_answer = "Resmi Gazete belgeleri işlenirken bir sorun oluştu."
            source_info += " (Hata: Formatlama)"
            retrieved_context = f"Formatlama Hatası: {e}"
            return {"answer": final_answer, "context": retrieved_context, "source": source_info}


    # 4. Eğer context varsa cevap üretiyoruz 
    if retrieved_context and not final_answer: # Context varsa ve henüz bir hata yoksa
        try:
            # app.core.llm'den varsayılan LLM'i alıyoruz
            logging.debug("LLM örneği alınıyor...")
            llm = get_llm()

            # LLM'e gönderilecek prompt'u hazırlıyoruz
            prompt = PROMPT_TEMPLATE.format(query=query, context=retrieved_context)
            logging.debug(f"LLM'e gönderilecek prompt (ilk 500 karakter):\n{prompt[:500]}...")

            # LLM'i çağırıyoruz ve cevabı alıyoruz
            logging.info("LLM çağrılıyor (generate_resmi_gazete_answer)...")
            llm_response = llm.invoke(prompt)
            final_answer = llm_response.content.strip()
            logging.info("LLM'den cevap alındı.")
            source_info += " (RAG ile Üretildi)"
        # Eğer LLM çağrılırken bir hata oluşursa, bunu yakalıyoruz
        except Exception as e:
            logging.error(f"Resmi Gazete cevabı üretilirken LLM hatası: {e}", exc_info=True)
            final_answer = "İlgili bilgiler bulundu ancak cevabı sentezlerken bir sorun oluştu."
            source_info += " (Hata: LLM)"

    logging.info(f"Resmi Gazete Agent tamamlandı. Cevap (ilk 100 karakter): '{final_answer[:100] if final_answer else 'Yok'}'")
    return {"answer": final_answer, "context": retrieved_context, "source": source_info}