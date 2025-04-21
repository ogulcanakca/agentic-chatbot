# configs/api_config.py

import logging
from dotenv import load_dotenv
from pathlib import Path

project_root = Path(__file__).resolve().parents[1] 
dotenv_path = project_root / ".env"

_env_loaded = False

def load_env():
    global _env_loaded
    if _env_loaded:
        return 

    if dotenv_path.is_file():
        load_dotenv(dotenv_path=dotenv_path, override=True) 
        logging.info(f"Environment variables from the .env file have been loaded: {dotenv_path}")
        _env_loaded = True
    else:
        load_dotenv(override=True) 
        logging.warning(f".env file not found: {dotenv_path}. System-wide or previously loaded environment variables will be used.")
        _env_loaded = True 

load_env()
