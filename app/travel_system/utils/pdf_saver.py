# app/travel_system/utils/pdf_saver.py

import os
import re
import logging 
import requests 
import io
import tempfile    
from pathlib import Path 
from fpdf import FPDF

# Logging ayarı
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

class TravelPDFSaver:
    def __init__(self, font_dir='assets/fonts', output_dir='plans'):
        # Temel dizinlerin mutlak yollarını Path nesnesi ile al
        base_dir = Path(font_dir).resolve() 
        output_base_dir = Path(output_dir).resolve()

        self.font_dir = str(base_dir) 
        self.output_dir = str(output_base_dir)

        # Font dosyaları için mutlak Path nesnelerini sakla
        self.regular_font_filename = 'DejaVuSansCondensed.ttf'
        self.bold_font_filename = 'DejaVuSansCondensed-Bold.ttf'
        self.regular_font_path_obj = base_dir / self.regular_font_filename
        self.bold_font_path_obj = base_dir / self.bold_font_filename
        
        # Başlatmada font dosyalarının varlığını kontrol et
        if not self.regular_font_path_obj.is_file():
             logging.error(f"Başlatma: Regular font bulunamadı! Yol: {self.regular_font_path_obj}")
             raise FileNotFoundError(f"Regular font not found at {self.regular_font_path_obj}. Please ensure fonts are in {self.font_dir}")
        if not self.bold_font_path_obj.is_file():
             logging.error(f"Başlatma: Bold font bulunamadı! Yol: {self.bold_font_path_obj}")
             raise FileNotFoundError(f"Bold font not found at {self.bold_font_path_obj}. Please ensure fonts are in {self.font_dir}")

        logging.info(f"PDF Saver başlatıldı. Font dizini (kontrol için): {self.font_dir}")
        logging.info(f"Kullanılacak regular font Path objesi: {self.regular_font_path_obj}")
        logging.info(f"Kullanılacak bold font Path objesi: {self.bold_font_path_obj}")

        # PDF oluşturma için temel ayarlar
        self.default_font_size = 11
        self.line_height = 6 # mm

        # Çıktı dizinini oluştur
        output_base_dir.mkdir(parents=True, exist_ok=True)

    # Metinden başlık çıkarmak için fonksiyon
    def extract_title(self, text):
        match = re.search(r'\*\*(.*?)\*\*', text)
        if match:
            title = match.group(1).strip()
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            safe_title = safe_title.replace(" ", "_")
            safe_title = safe_title[:50]
            # return ifadesi if bloğu içinde kalmalı
            if safe_title:
                 return safe_title
            else:
                 return "seyahat_plani" # Başlık çıkarılamazsa veya boşsa
        return "seyahat_plani" # Eşleşme olmazsa

    # Benzersiz PDF dosya adı oluşturmak için fonksiyon
    def generate_unique_filename(self, base_name="Travel_plan"):
        if base_name.lower().endswith('.pdf'):
            base_name = base_name[:-4]

        output_path_obj = Path(self.output_dir)
        counter = 1
        while True:
            filename = f"{base_name}_{counter}.pdf"
            file_path = output_path_obj / filename
            if not file_path.exists():
                return filename
            counter += 1

    # Harita URL'sini işle ve geçici dosya olarak kaydet
    def download_map_image(self, map_url):
        try:
            # Görseli indir
            headers = {'User-Agent': 'Mozilla/5.0'} 
            response = requests.get(map_url, stream=True, timeout=15, headers=headers) 
            response.raise_for_status() 
            
            # İçerik tipini kontrol et
            content_type = response.headers.get('content-type', '').lower()
            image_type = 'PNG'; 
            if 'png' in content_type: image_type = 'PNG'
            elif 'jpeg' in content_type or 'jpg' in content_type: image_type = 'JPG'
            elif content_type: logging.warning(f"Desteklenmeyen harita formatı: {content_type}. PNG varsayılacak.")
            else: logging.warning("Harita içerik tipi alınamadı. PNG varsayılıyor.")
            
            # Geçici dosya oluştur ve içeriği yaz
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=f'.{image_type.lower()}')
            temp_file.write(response.content)
            temp_file.close()
            
            logging.info(f"Harita görseli geçici dosyaya kaydedildi: {temp_file.name}")
            return temp_file.name, image_type
        except Exception as e:
            logging.error(f"Harita indirirken hata: {e}", exc_info=True)
            return None, None

    # Ana PDF oluşturma fonksiyonu
    def save_travel_plan_to_pdf(self, plan_text, filename=None):
        
        pdf = FPDF()
        pdf.add_page()

        try:
            # Mutlak yolu al, slash'ları düzelt ve varlığını SON KEZ kontrol et
            regular_font_path_str = str(self.regular_font_path_obj.resolve()).replace('\\', '/')
            bold_font_path_str = str(self.bold_font_path_obj.resolve()).replace('\\', '/')
            
            logging.info(f"add_font için Regular Path: {regular_font_path_str}")
            if not os.path.exists(regular_font_path_str):
                 logging.error(f"HATA: Regular font add_font öncesi BULUNAMADI: {regular_font_path_str}")
                 raise FileNotFoundError(f"Cannot find regular font right before add_font: {regular_font_path_str}")
            pdf.add_font('DejaVu', '', regular_font_path_str, uni=True) 
            
            logging.info(f"add_font için Bold Path: {bold_font_path_str}")
            if not os.path.exists(bold_font_path_str):
                 logging.error(f"HATA: Bold font add_font öncesi BULUNAMADI: {bold_font_path_str}")
                 raise FileNotFoundError(f"Cannot find bold font right before add_font: {bold_font_path_str}")
            pdf.add_font('DejaVu', 'B', bold_font_path_str, uni=True) 
            
            # İtalik font kullanımı için normal font ile yerleştirme
            pdf.add_font('DejaVu', 'I', regular_font_path_str, uni=True)
            
            logging.info("fpdf.add_font çağrıları başarıyla yapıldı (mutlak yolla).")
        except Exception as font_err:
             logging.error(f"fpdf font eklerken KRİTİK hata oluştu: {font_err}", exc_info=True)
             raise RuntimeError(f"PDF fontları eklenemedi (mutlak yol denemesine rağmen): {font_err}") from font_err

        # Öncelikle tüm harita URL'lerini bul ve indir
        map_url_pattern = r"(https?://api\.tomtom\.com/map/1/staticimage[^\s]+)"
        map_matches = re.findall(map_url_pattern, plan_text)
        map_files = []
        
        # Tüm harita URL'lerini indir ve geçici dosyalara kaydet
        for map_url in map_matches:
            temp_file_path, image_type = self.download_map_image(map_url)
            if temp_file_path:
                map_files.append((map_url, temp_file_path, image_type))
                logging.info(f"Harita URL'si {map_url} için geçici dosya hazırlandı.")
            else:
                logging.error(f"Harita URL'si {map_url} indirilemedi.")
                
        # Şimdi metni satır satır işle
        lines = plan_text.strip().split('\n')

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                pdf.ln(self.line_height / 2)
                continue
            
            # Harita referansını içeren satırı tespit et
            map_url = None
            for url, _, _ in map_files:
                if url in line:
                    map_url = url
                    break
                    
            if map_url:
                # Bu satır bir harita referansı içeriyor
                
                # URL'yi içeren metni, URL hariç ekleyelim
                clean_text = re.sub(map_url_pattern, "", line).strip()
                if clean_text:
                    # Temiz metin içeriğini ekle
                    pdf.set_font('DejaVu', '', self.default_font_size)
                    if clean_text.endswith(":"):
                        pdf.multi_cell(0, self.line_height, clean_text, border=0, align='L')
                    else:
                        pdf.multi_cell(0, self.line_height, f"{clean_text}:", border=0, align='L')
                else:
                    # Hiç metin yoksa, sadece "Harita görünümü:" yaz
                    pdf.set_font('DejaVu', '', self.default_font_size)
                    pdf.multi_cell(0, self.line_height, "Harita görünümü:", border=0, align='L')
                
                # Harita resmini ekle
                map_index = next((i for i, (url, _, _) in enumerate(map_files) if url == map_url), None)
                if map_index is not None:
                    _, temp_file_path, image_type = map_files[map_index]
                    available_width = pdf.w - pdf.l_margin - pdf.r_margin
                    
                    try:
                        # Yeni pozisyon belirle
                        pdf.ln(self.line_height * 0.5)
                        
                        # Resmi ekle
                        pdf.image(name=temp_file_path, type=image_type, w=available_width)
                        pdf.ln(self.line_height)
                        logging.info(f"Harita görseli PDF'e eklendi: {temp_file_path}")
                        
                        # URL referansı artık eklenmeyecek
                    except Exception as img_err:
                        logging.error(f"PDF'e harita eklerken hata: {img_err}", exc_info=True)
                        pdf.multi_cell(0, self.line_height, f"[Harita görseli eklenemedi]", border=0, align='L')
                continue  # Satırı işledik, devam et
            
            # Başlık kontrolü
            heading_match = re.match(r'^(\d+\.)\s*(\*\*.*?\*\*)', line)
            if heading_match:
                number_part = heading_match.group(1)
                bold_part = heading_match.group(2)
                text_inside = bold_part[2:-2].strip()
                pdf.set_font('DejaVu', 'B', self.default_font_size + 1) 
                pdf.multi_cell(0, self.line_height, f"{number_part} {text_inside}", border=0, align='L')
                pdf.ln(self.line_height * 0.5)
                continue # Sonraki satıra geç

            # Madde işareti kontrolü
            elif line.startswith('* '):
                pdf.set_x(pdf.l_margin + 5) 
                pdf.set_font('DejaVu', '', self.default_font_size)
                content = line[2:]
                parts = re.split(r'(\*\*.*?\*\*)', content)
                is_first_part = True # Write sonrası boşluk için flag
                for part in parts:
                    if not part: 
                        continue
                    # İlk parçadan sonra ve satır başında değilsek boşluk ekle
                    if not is_first_part and pdf.get_x() > (pdf.l_margin + 5): 
                         pdf.write(self.line_height, " ") 
                         
                    if part.startswith('**') and part.endswith('**'):
                        pdf.set_font('DejaVu', 'B', self.default_font_size)
                        pdf.write(self.line_height, part[2:-2])
                        pdf.set_font('DejaVu', '', self.default_font_size)
                    else:
                        pdf.write(self.line_height, part)
                    is_first_part = False
                pdf.ln(self.line_height)
                pdf.set_x(pdf.l_margin) # Bir sonraki olası madde için x'i sıfırla
                continue # Sonraki satıra geç

            # Sadece kalın olan başlık kontrolü (genellikle alt başlık)
            elif line.startswith('**') and line.endswith('**') and len(line) > 4:
                  pdf.set_font('DejaVu', 'B', self.default_font_size)
                  text_inside = line[2:-2]
                  pdf.multi_cell(0, self.line_height, text_inside, border=0, align='L')
                  pdf.ln(self.line_height * 0.3) # Başlık sonrası daha az boşluk
                  continue # Sonraki satıra geç
                  
            # Düz metin veya içinde kalın geçen metin
            else: 
                  pdf.set_font('DejaVu', '', self.default_font_size)
                  parts = re.split(r'(\*\*.*?\*\*)', line)
                  is_first_part = True # Write sonrası boşluk için flag
                  for part in parts:
                     if not part: 
                         continue
                     # İlk parçadan sonra ve satır başında değilsek boşluk ekle
                     if not is_first_part and pdf.get_x() > pdf.l_margin : 
                          pdf.write(self.line_height, " ") 
                     if part.startswith('**') and part.endswith('**'):
                          pdf.set_font('DejaVu', 'B', self.default_font_size)
                          pdf.write(self.line_height, part[2:-2])
                          pdf.set_font('DejaVu', '', self.default_font_size)
                     else:
                          pdf.write(self.line_height, part)
                     is_first_part = False
                  pdf.ln(self.line_height) # Satır sonu
                  continue # Sonraki satıra geç

        # --- PDF Kaydetme ---
        if filename: 
            base_name = filename
        else: 
            base_name = self.extract_title(plan_text) # Başlığı kullan
            
        final_filename = self.generate_unique_filename(base_name)
        output_path = Path(self.output_dir) / final_filename
        output_path_str = str(output_path)

        try:
            logging.info(f"PDF '{output_path_str}' olarak kaydediliyor...")
            pdf.output(output_path_str, 'F') 
            print(f"Seyahat planı '{output_path_str}' olarak kaydedildi.") 
            
            # Geçici dosyaları temizle
            for _, temp_file_path, _ in map_files:
                try:
                    os.unlink(temp_file_path)
                    logging.info(f"Geçici dosya silindi: {temp_file_path}")
                except:
                    logging.warning(f"Geçici dosya silinemedi: {temp_file_path}")
                    
            return output_path_str 
        except Exception as e:
            print(f"PDF dosyası kaydedilirken hata oluştu: {e}") 
            logging.error(f"PDF dosyası kaydedilirken nihai hata oluştu ({output_path_str}): {e}", exc_info=True)
            
            # Hata durumunda da geçici dosyaları temizle
            for _, temp_file_path, _ in map_files:
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                    
            raise RuntimeError(f"PDF could not be saved: {e}") from e