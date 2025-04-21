# app/core/state.py
from typing import Optional, TypedDict

# AgentState tanımını buraya taşıdık
class AgentState(TypedDict):
    query: str
    classification: Optional[str]
    context: Optional[str]
    answer: Optional[str]
    source: Optional[str]
    pdf_path: Optional[str] # Seyahat planı PDF yolu için

    # --- Agentic RAG için Alanlar ---
    uploaded_file_data: Optional[bytes] # Yüklenen dosyanın içeriği (byte)
    uploaded_file_name: Optional[str] # Yüklenen dosyanın adı
    route_directly_to_agentic_rag: Optional[bool] # Doğrudan yönlendirme işareti
    # --- BİTTİ: Agentic RAG için Alanlar ---

    # İsteğe bağlı: Mesaj geçmişi için
    # messages: Optional[List[dict]]