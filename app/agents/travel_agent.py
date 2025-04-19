# app/agents/travel_agent.py
import logging
import sys
from pathlib import Path
from typing import Dict, Any
import asyncio # asyncio'yu import et

# Proje kök dizinini sys.path'e ekleme
project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

# Seyahat sistemi sınıfını ve PDF kaydediciyi import et
try:
    # Dosyayı app/travel_system/workflow.py olarak kaydettiyseniz:
    from app.travel_system.workflow import TravelPlanningSystem 
    from app.travel_system.utils.pdf_saver import TravelPDFSaver
except ImportError as e:
     logging.error(f"Travel system bileşenleri import edilemedi: {e}")
     # Bu durumda agent'ın çalışmasını engelleyecek bir mekanizma eklenebilir
     # veya başlatmada hata vermesi sağlanabilir. Şimdilik devam ediyoruz.
     TravelPlanningSystem = None 
     TravelPDFSaver = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# Bu objeleri globalde başlatmak yerine fonksiyon içinde başlatmak
# veya None kontrolü yapmak daha güvenli olabilir, özellikle import hatalarında.
pdf_saver = None
travel_system = None

if TravelPDFSaver:
     try:
          pdf_saver = TravelPDFSaver(
               font_dir=str(project_root / "assets/fonts"), 
               output_dir=str(project_root / "plans")
          )
     except FileNotFoundError as fnf_error:
          logging.error(f"PDF Saver başlatılamadı (Font dosyası hatası): {fnf_error}")
     except Exception as saver_err:
          logging.error(f"PDF Saver başlatılırken hata: {saver_err}")

if TravelPlanningSystem:
     try:
          travel_system = TravelPlanningSystem() # Seyahat LangGraph sistemini başlatır
     except Exception as system_err:
          logging.error(f"TravelPlanningSystem başlatılırken hata: {system_err}")
          travel_system = None # Başlatılamazsa None yap

# Fonksiyonu SENKRON 'def' olarak değiştir
def handle_travel_query(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Kullanıcının seyahat sorgusunu alır, TravelPlanningSystem'i (asenkron olarak)
    çalıştırır, sonucu ve PDF yolunu (varsa) state'e ekler.
    """
    logging.info("Travel Agent çalıştırılıyor...")
    query: str = state.get("query", "")
    pdf_path: str | None = None 
    answer: str = "Seyahat planı oluşturulamadı." 

    # Başlatma sırasında hata olduysa veya import edilemediyse erken çık
    if not travel_system:
         logging.error("Travel Agent: TravelPlanningSystem örneği mevcut değil.")
         return {"answer": "Seyahat planlama sistemi şu anda kullanılamıyor.", "source": "Travel Agent (Hata)"}
    if not pdf_saver:
         logging.warning("Travel Agent: PDF Saver örneği mevcut değil. PDF kaydedilemeyecek.")
         # PDF kaydedilemese de devam edebiliriz.

    if not query:
        logging.warning("Travel Agent: State'de sorgu bulunamadı.")
        return {"answer": "Lütfen bir seyahat sorgusu girin.", "source": "Travel Agent (Hata)"}

    try:
        logging.info(f"TravelPlanningSystem'e gönderilecek sorgu: '{query}'")
        
        # --- ASENKRON ÇAĞRIYI BURADA asyncio.run İLE YAP ---
        # travel_system.process_query asenkron olduğu için asyncio.run kullanılır.
        # Not: Eğer zaten çalışan bir asyncio döngüsü varsa (Streamlit'in kendi döngüsü gibi),
        # asyncio.run yerine döngüye erişip run_until_complete kullanmak gerekebilir,
        # ancak genellikle basit Streamlit kullanımlarında asyncio.run çalışır.
        final_plan = asyncio.run(travel_system.process_query(query))
        # --- ---

        logging.info("TravelPlanningSystem tamamlandı.")

        if final_plan and isinstance(final_plan, str) and not final_plan.startswith("An error occurred") and not final_plan.startswith("Could not generate"):
            answer = final_plan
            logging.info("Seyahat planı başarıyla oluşturuldu.")
            # PDF kaydetme (sadece pdf_saver varsa)
            if pdf_saver:
                 try:
                      base_filename = pdf_saver.extract_title(final_plan)
                      pdf_path = pdf_saver.save_travel_plan_to_pdf(final_plan, filename=base_filename)
                      logging.info(f"Seyahat planı PDF olarak kaydedildi: {pdf_path}")
                 except Exception as pdf_err:
                      logging.error(f"Seyahat planı PDF'ye kaydedilemedi: {pdf_err}", exc_info=True)
            else:
                 logging.info("PDF Saver mevcut olmadığından PDF kaydedilmedi.")
        else:
             # process_query'den dönen hata mesajını veya geçersiz sonucu logla/kullan
             error_detail = final_plan if isinstance(final_plan, str) else "Geçersiz formatta sonuç döndü."
             logging.error(f"TravelPlanningSystem bir hata döndürdü veya boş/geçersiz sonuç verdi: {error_detail}")
             answer = final_plan # Hata mesajını veya sonucu döndür

    except RuntimeError as e:
         # asyncio.run() iç içe döngü hatası verirse logla
         if "cannot run coroutine" in str(e):
              logging.error("asyncio.run() hatası: Muhtemelen zaten çalışan bir event loop var.", exc_info=True)
              answer = "Seyahat planı işlenirken asenkron bir hata oluştu. Lütfen tekrar deneyin veya yöneticiye başvurun."
         else:
              logging.error(f"Travel Agent sırasında Runtime hatası oluştu: {e}", exc_info=True)
              answer = f"Seyahat planı işlenirken bir çalışma zamanı hatası oluştu: {type(e).__name__}"
    except Exception as e:
        logging.error(f"Travel Agent sırasında beklenmedik bir hata oluştu: {e}", exc_info=True)
        answer = f"Seyahat planı işlenirken beklenmedik bir hata oluştu: {type(e).__name__}"

    return {
        "answer": answer,
        # PDF yolu null değilse kaynak bilgisine ekle
        "source": "Travel Agent" + (f" (PDF: {Path(pdf_path).name})" if pdf_path else ""), 
        "pdf_path": pdf_path 
    }