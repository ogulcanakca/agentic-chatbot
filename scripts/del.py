# scripts/del.py

import shutil
from pathlib import Path

def delete_data_directory(data_dir_path):
    data_dir = Path(data_dir_path)
    if data_dir.exists() and data_dir.is_dir():
        try:
            shutil.rmtree(data_dir)
            print(f"The data directory '{data_dir_path}' and its contents were successfully deleted.")
        except OSError as e:
            print(f"An error occurred while deleting the directory '{data_dir_path}': {e}")
    else:
        print(f"The path '{data_dir_path}' either does not exist or is not a directory.")

if __name__ == "__main__":
    data_directory_to_delete = Path(__file__).resolve().parents[1] / "data"
    delete_data_directory(data_directory_to_delete)
