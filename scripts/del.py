# scripts/del.py

import shutil
from pathlib import Path

def delete_data_directory(data_dir_path):
    data_dir = Path(data_dir_path)
    if data_dir.exists() and data_dir.is_dir():
        try:
            shutil.rmtree(data_dir)
            print(f"'{data_dir_path}' veri dizini ve içeriği başarıyla silindi.")
        except OSError as e:
            print(f"'{data_dir_path}' dizini silinirken hata oluştu: {e}")
    else:
        print(f"'{data_dir_path}' veri dizini mevcut değil veya bir dizin değil.")

if __name__ == "__main__":
    data_directory_to_delete = Path(__file__).resolve().parents[1] / "data"
    delete_data_directory(data_directory_to_delete)
