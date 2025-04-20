# app/agents/travel_agent.py
import logging
import sys
from pathlib import Path
from typing import Dict, Any
# import asyncio # ARTIK GEREKLİ DEĞİL

# Proje kökünü ekle
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Global başlatmayı kaldır (fonksiyon içinde başlatmak daha güvenli)
# travel_system = None
# pdf_saver = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

# Fonksiyon SENKRON kalır
def handle_travel_query(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Seyahat sorgularını SENKRON TravelPlanningSystem kullanarak işler.
    """
    logging.info("Travel Agent çalıştırılıyor (SENKRON MOD)...")
    query: str = state.get("query", "")
    pdf_path: str | None = None
    answer: str = "Seyahat planı oluşturulamadı."

    # Bileşenleri fonksiyon içinde başlat (daha güvenli)
    travel_system = None
    pdf_saver = None
    try:
        # Gerekli sınıfları import et
        from app.travel_system.workflow import TravelPlanningSystem # Senkron versiyonu import edecek
        from app.travel_system.utils.pdf_saver import TravelPDFSaver

        # TravelPlanningSystem'i başlat
        try:
            travel_system = TravelPlanningSystem() # Senkron sistem başlatılıyor
            logging.info("TravelPlanningSystem (Senkron) başarıyla başlatıldı.")
        except Exception as system_err:
            logging.error(f"TravelPlanningSystem (Senkron) başlatılırken hata: {system_err}", exc_info=True)
            return {"answer": f"Seyahat sistemi başlatılamadı: {type(system_err).__name__}", "source": "Travel Agent (Hata)"}

        # PDF Saver'ı başlat
        try:
             pdf_saver = TravelPDFSaver(
                 font_dir=str(project_root / "assets/fonts"),
                 output_dir=str(project_root / "plans")
             )
             logging.info("TravelPDFSaver başarıyla başlatıldı.")
        except FileNotFoundError as fnf_error:
             logging.warning(f"PDF Saver başlatılamadı (Font dosyası hatası): {fnf_error}. PDF kaydedilmeyecek.")
             pdf_saver = None
        except Exception as saver_err:
             logging.error(f"PDF Saver başlatılırken genel hata: {saver_err}")
             pdf_saver = None

    except ImportError as e:
        logging.error(f"Travel system veya PDF saver bileşenleri import edilemedi: {e}")
        return {"answer": "Seyahat planlama sistemi bileşenleri bulunamadı.", "source": "Travel Agent (Hata)"}

    # Sorgu kontrolü
    if not query:
        logging.warning("Travel Agent: State'de sorgu bulunamadı.")
        return {"answer": "Lütfen bir seyahat sorgusu girin.", "source": "Travel Agent (Hata)"}

    # Ana işlem bloğu (SENKRON)
    try:
        logging.info(f"TravelPlanningSystem (Senkron)'e gönderilecek sorgu: '{query}'")

        # --- DOĞRUDAN SENKRON ÇAĞRI ---
        final_plan = travel_system.process_query(query)
        # --- ---

        logging.info("TravelPlanningSystem (Senkron) tamamlandı.")

        # Sonuç işleme ve PDF kaydetme (aynı kalır)
        if final_plan and isinstance(final_plan, str) and not final_plan.startswith("An error occurred") and not final_plan.startswith("Could not generate"):
            answer = final_plan
            logging.info("Seyahat planı başarıyla oluşturuldu.")
            if pdf_saver:
                try:
                    base_filename = pdf_saver.extract_title(final_plan) # Bu metodun varlığını kontrol et
                    pdf_path = pdf_saver.save_travel_plan_to_pdf(final_plan, filename=base_filename)
                    logging.info(f"Seyahat planı PDF olarak kaydedildi: {pdf_path}")
                except AttributeError:
                     logging.error("PDF Saver'da 'extract_title' metodu bulunamadı.")
                except Exception as pdf_err:
                    logging.error(f"Seyahat planı PDF'ye kaydedilemedi: {pdf_err}", exc_info=True)
            else:
                logging.info("PDF Saver başlatılamadığı veya mevcut olmadığından PDF kaydedilmedi.")
        else:
            error_detail = final_plan if isinstance(final_plan, str) else "Geçersiz formatta sonuç döndü."
            logging.error(f"TravelPlanningSystem (Senkron) bir hata döndürdü veya boş/geçersiz sonuç verdi: {error_detail}")
            answer = final_plan if final_plan else "Beklenmedik bir sonuç alındı."


    # Hata yönetimi (asyncio hataları artık beklenmez)
    except Exception as e:
        logging.error(f"Travel Agent (Senkron) sırasında beklenmedik bir hata oluştu: {e}", exc_info=True)
        answer = f"Seyahat planı işlenirken beklenmedik bir hata oluştu: {type(e).__name__}"

    # Sonucu döndür
    return {
        "answer": answer,
        "source": "Travel Agent (Senkron)" + (f" (PDF: {Path(pdf_path).name})" if pdf_path else ""),
        "pdf_path": pdf_path
    }