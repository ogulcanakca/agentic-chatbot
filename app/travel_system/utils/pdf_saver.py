# utils/pdf_saver.py

import os
import re
import shutil
from fpdf import FPDF

class TravelPDFSaver:
    def __init__(self, font_dir='assets/fonts', output_dir='plans'):
        # Convert relative paths to absolute paths
        self.font_dir = os.path.abspath(font_dir)
        self.output_dir = os.path.abspath(output_dir)
        
        # Create necessary directories
        self.ensure_font_directory()
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Set font paths
        self.regular_font_path = os.path.join(self.font_dir, 'DejaVuSansCondensed.ttf')
        self.bold_font_path = os.path.join(self.font_dir, 'DejaVuSansCondensed-Bold.ttf')

        # Check if font files exist, download if they don't
        if not os.path.exists(self.regular_font_path) or not os.path.exists(self.bold_font_path):
            self.download_fonts()

        self.default_font_size = 11
        self.line_height = 6 # mm

    def ensure_font_directory(self):
        """Make sure the fonts directory exists in the locations FPDF expects"""
        # Create project font directory
        os.makedirs(self.font_dir, exist_ok=True)
        
        # Create fpdf expected font directory (relative to current working directory)
        os.makedirs('fonts', exist_ok=True)

    def download_fonts(self):
        """Download or copy DejaVu fonts to the necessary locations"""
        # This is a simplified version - in a real app, you would download from a URL
        # For this example, we'll assume you might have the fonts elsewhere and copy them
        
        # First check if the fonts are in the alternate location
        alternate_font_dir = 'fonts'
        alternate_regular = os.path.join(alternate_font_dir, 'DejaVuSansCondensed.ttf')
        alternate_bold = os.path.join(alternate_font_dir, 'DejaVuSansCondensed-Bold.ttf')
        
        if os.path.exists(alternate_regular) and os.path.exists(alternate_bold):
            # Copy from alternate location to our font directory
            shutil.copy2(alternate_regular, self.regular_font_path)
            shutil.copy2(alternate_bold, self.bold_font_path)
            print(f"Fonts copied from alternate location to {self.font_dir}")
        else:
            # If files don't exist, we'd normally download them
            # But for simplicity, we'll raise an error with clear instructions
            raise FileNotFoundError(
                f"Font files not found. Please place DejaVuSansCondensed.ttf and "
                f"DejaVuSansCondensed-Bold.ttf in either '{self.font_dir}' or 'fonts/' directory."
            )
            
        # Ensure the fonts are also in the directory FPDF expects
        if not os.path.exists('fonts/DejaVuSansCondensed.ttf'):
            shutil.copy2(self.regular_font_path, 'fonts/DejaVuSansCondensed.ttf')
        if not os.path.exists('fonts/DejaVuSansCondensed-Bold.ttf'):
            shutil.copy2(self.bold_font_path, 'fonts/DejaVuSansCondensed-Bold.ttf')

    def extract_title(self, text):
        match = re.search(r'\*\*(.*?)\*\*', text)
        if match:
            title = match.group(1).strip()
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            safe_title = safe_title.replace(" ", "_")
            safe_title = safe_title[:50]
            return safe_title if safe_title else "seyahat_plani"
        return "seyahat_plani"

    def generate_unique_filename(self, base_name="Travel_plan"):
        if base_name.lower().endswith('.pdf'):
            base_name = base_name[:-4]

        counter = 1
        while True:
            filename = f"{base_name}_{counter}.pdf"
            file_path = os.path.join(self.output_dir, filename)
            if not os.path.exists(file_path):
                return filename
            counter += 1

    def save_travel_plan_to_pdf(self, plan_text, filename=None):
        # Make sure fonts are in place before starting
        if not os.path.exists('fonts/DejaVuSansCondensed.ttf') or not os.path.exists('fonts/DejaVuSansCondensed-Bold.ttf'):
            self.download_fonts()
            
        pdf = FPDF()
        pdf.add_page()

        # Add fonts using font name that FPDF can find in the 'fonts' directory
        pdf.add_font('DejaVu', '', 'fonts/DejaVuSansCondensed.ttf', uni=True)
        pdf.add_font('DejaVu', 'B', 'fonts/DejaVuSansCondensed-Bold.ttf', uni=True)

        lines = plan_text.strip().split('\n')

        for line in lines:
            line = line.strip()

            if not line:
                pdf.ln(self.line_height / 2)
                continue

            heading_match = re.match(r'^(\d+\.)\s*(\*\*.*?\*\*)', line)
            if heading_match:
                number_part = heading_match.group(1)
                bold_part = heading_match.group(2)
                text_inside = bold_part[2:-2].strip()
                
                pdf.set_font('DejaVu', 'B', self.default_font_size + 1)
                pdf.multi_cell(0, self.line_height, f"{number_part} {text_inside}", border=0, align='L')
                pdf.ln(self.line_height * 0.5)
                continue

            elif line.startswith('* '):
                pdf.set_x(pdf.l_margin + 5)
                pdf.set_font('DejaVu', '', self.default_font_size)
                content = line[2:]
                
                parts = re.split(r'(\*\*.*?\*\*)', content)
                current_x = pdf.get_x() 
                for i, part in enumerate(parts):
                    if not part: continue
                    
                    part_width = pdf.get_string_width(part[2:-2] if part.startswith('**') else part)
                    remaining_width = pdf.w - pdf.r_margin - pdf.get_x()

                    
                    if part.startswith('**') and part.endswith('**'):
                        pdf.set_font('DejaVu', 'B', self.default_font_size)
                        pdf.write(self.line_height, part[2:-2])
                        pdf.set_font('DejaVu', '', self.default_font_size)
                    else:
                        pdf.write(self.line_height, part)
                
                pdf.ln(self.line_height)
                pdf.set_x(pdf.l_margin) 
                continue

            elif line.startswith('**') and line.endswith('**') and len(line) > 4:
                pdf.set_font('DejaVu', 'B', self.default_font_size)
                text_inside = line[2:-2]
                pdf.multi_cell(0, self.line_height, text_inside, border=0, align='L')
                pdf.ln(self.line_height * 0.3)
                continue

            else:
                pdf.set_font('DejaVu', '', self.default_font_size)
                parts = re.split(r'(\*\*.*?\*\*)', line)
                current_x = pdf.get_x() 
                for i, part in enumerate(parts):
                    if not part: continue
                    
                    if part.startswith('**') and part.endswith('**'):
                        pdf.set_font('DejaVu', 'B', self.default_font_size)
                        pdf.write(self.line_height, part[2:-2])
                        pdf.set_font('DejaVu', '', self.default_font_size)
                    else:
                         pdf.write(self.line_height, part)
                         
                pdf.ln(self.line_height) 
                pdf.set_x(pdf.l_margin) 

        if filename:
            base_name = filename
            if base_name.lower().endswith('.pdf'):
                base_name = base_name[:-4]
            final_filename = self.generate_unique_filename(base_name)
        else:
            final_filename = self.generate_unique_filename() 

        output_path = os.path.join(self.output_dir, final_filename)

        if os.path.exists(output_path):
             temp_base = final_filename[:-4]
             match = re.match(r'(.*)_(\d+)$', temp_base)
             if match:
                 actual_base = match.group(1)
                 final_filename = self.generate_unique_filename(actual_base)
             else:
                 final_filename = self.generate_unique_filename(temp_base)
             output_path = os.path.join(self.output_dir, final_filename)

        try:
            pdf.output(output_path, 'F')
            print(f"Seyahat planı '{output_path}' olarak kaydedildi.")
            return output_path
        except Exception as e:
            print(f"PDF dosyası kaydedilirken hata oluştu: {e}")
            # Print more detailed error information
            import traceback
            traceback.print_exc()
            raise e