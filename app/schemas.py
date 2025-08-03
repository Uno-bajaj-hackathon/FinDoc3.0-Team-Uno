from pydantic import BaseModel
from typing import List, Any, Optional, Union

class RunRequest(BaseModel):
    documents: Union[str, List[str]] 
    questions: List[str] # Accept both single string and array    questions: List[str]

class Citation(BaseModel):
    clause_id: str
    text: str
    relevance_score: float

class Answer(BaseModel):
    question: str
    short_answer: str
    claim_probability: Optional[float] = None
    risk_assessment: Optional[dict] = None
    citations: Optional[List[Citation]] = None
    processing_time_ms: Optional[int] = None

class RunResponse(BaseModel):
    answers: List[str]
