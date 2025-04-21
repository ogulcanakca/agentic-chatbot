# app/utils/embedding.py

import logging
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import torch
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')

project_root = Path(__file__).resolve().parents[2]
sys.path.append(str(project_root))

from configs.app_config import MODEL_NAME

# Our global variable where we store the model object with a simple cache mechanism
model: Optional[SentenceTransformer] = None

# We define a function to load the model
def get_embedding_model() -> SentenceTransformer:

    global model
    if model is None:
        logging.info(f"Loading model '{MODEL_NAME}'...")
        
        # We use GPU if available, otherwise continue with CPU.
        # The system works fast even though I worked on CPU throughout the process
        device = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
        logging.info(f"Device to be used: {device}")

        # We load the model
        model = SentenceTransformer(MODEL_NAME, device=device)

        logging.info(f"Model '{MODEL_NAME}' successfully loaded ({device}).")
        
    return model

# We define a function for embedding generation
def generate_embeddings(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    if not texts:
        logging.warning("Empty text list received for embedding generation.")
        return []

    try:
        model = get_embedding_model()
        logging.info(f"Generating embeddings for {len(texts)} texts (batch size: {batch_size})...")

        # We generate embeddings using the model
        embeddings_np = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True
        )
        logging.info("Embedding generation completed.")

        # We convert NumPy arrays to lists for storage and use in JSON
        embeddings_list = embeddings_np.tolist()
        return embeddings_list
    
     # We return an empty list in case of error
    except Exception as e:
        logging.error(f"Error occurred during embedding generation: {e}", exc_info=True)
        return []
