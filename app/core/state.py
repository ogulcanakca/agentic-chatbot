# app/core/state.py

from typing import Optional, TypedDict

class AgentState(TypedDict):
    query: str
    classification: Optional[str]
    context: Optional[str]
    answer: Optional[str]
    source: Optional[str]
    pdf_path: Optional[str] 

    uploaded_file_data: Optional[bytes]
    uploaded_file_name: Optional[str] 
    route_directly_to_agentic_rag: Optional[bool] 
