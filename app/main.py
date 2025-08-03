from fastapi import FastAPI, HTTPException, Depends, Header
from typing import List
import time
import uuid

from .config import settings
from .schemas import RunRequest, RunResponse
from .ingestion import download_blob, extract_text, chunk, Clause
from .vector_store import QdrantVectorStore  # Updated import
from .risk_engine import RiskAssessmentEngine
from .llm_reasoner import GPT4oMiniReasoner  # New import
from .dataset_loader import PolicyDatasetLoader
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app = FastAPI(title="LLM Query–Retrieval System with GPT-4o Mini + Qdrant")

app.mount("/css", StaticFiles(directory="static/css"), name="css")
app.mount("/js", StaticFiles(directory="static/js"), name="js")
app.mount("/static", StaticFiles(directory="static"), name="static")


# Add after your existing app initialization

# Serve your index.html at the root
@app.get("/")
async def serve_frontend():
    return FileResponse("static/index.html")
# Initialize components
vector_store = QdrantVectorStore()
risk_engine = RiskAssessmentEngine()
llm_reasoner = GPT4oMiniReasoner()  # New reasoner
dataset_loader = PolicyDatasetLoader()

def auth(auth_header: str = Header(..., alias="Authorization")):
    if auth_header.replace("Bearer ", "") != settings.bearer:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/api/v1/hackrx/run", dependencies=[Depends(auth)])
async def run(req: RunRequest):
    t0 = time.time()
    all_clauses: List[Clause] = []

    # 1) Document ingestion
    documents_list = [req.documents] if isinstance(req.documents, str) else req.documents
    for url in documents_list:
        doc_id = uuid.uuid4().hex[:8]
        fp = await download_blob(url)
        raw = extract_text(fp)
        clauses = chunk(raw, doc_id)
        all_clauses.extend(clauses)

    # Add local sample policies
    # sample_clauses = dataset_loader.load_sample_policies()
    # all_clauses.extend(sample_clauses)

    # 2) Add to vector store
    vector_store.clear_collection()
    if all_clauses:
        vector_store.add_clauses(all_clauses)
        print(f"✅ Indexed {len(all_clauses)} clauses from hackathon policy only")

    # 3) Process questions - SIMPLIFIED FORMAT
    # Remove the standalone function and update the endpoint logic:
    answers = []
    for question in req.questions:
        # Semantic search
        relevant_clauses = vector_store.search(question, k=5)  # Increased from 3 to 5
        
        if not relevant_clauses:
            answers.append("No relevant information found in the provided documents.")
            continue

        # Extract clause objects
        clause_objects = [clause for clause, _, _ in relevant_clauses]
        risk_analysis = risk_engine.assess_claim_risk(clause_objects, question)
        
        # Use the proper LLM reasoner class
        llm_result = llm_reasoner.generate_answer(question, clause_objects, risk_analysis)
        
        # Extract the answer
        if isinstance(llm_result, dict) and "answer" in llm_result:
            answer_text = llm_result["answer"]
        else:
            answer_text = str(llm_result)
        
        answers.append(answer_text)

    return {"answers": answers}

# Add these imports to your existing main.py
from .policy_analyzer import PolicyAnalyzer

# Initialize the policy analyzer (add this after your other initializations)
policy_analyzer = PolicyAnalyzer(risk_engine)

# Add these 3 endpoints to your main.py:

@app.post("/api/v1/hackrx/compare-policies", dependencies=[Depends(auth)])
async def compare_policies(req: RunRequest):
    """Compare how multiple policies handle specific questions"""
    t0 = time.time()
    
    # Load sample policies + any additional documents
    all_clauses = []
    
    
    # Handle single document string format
    documents_list = [req.documents] if isinstance(req.documents, str) else req.documents
    
    if len(documents_list) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 policies for comparison")
    
    # Add any remote documents
    for i, url in enumerate(documents_list):
        doc_id = f"policy_{i+1}_{uuid.uuid4().hex[:8]}"
        fp = await download_blob(url)
        raw = extract_text(fp)
        clauses = chunk(raw, doc_id)
        all_clauses.extend(clauses)
    
    # Run comparisons for each question
    comparisons = []
    for question in req.questions:
        comparison = policy_analyzer.compare_policies(question, all_clauses)
        comparisons.append(comparison)
    
    return {
        "comparisons": comparisons,
        "processing_time_ms": int((time.time() - t0) * 1000),
        "total_policies": len(set(clause.id.split('_')[0] for clause in all_clauses))
    }

@app.post("/api/v1/hackrx/coverage-gaps", dependencies=[Depends(auth)])
async def analyze_coverage_gaps(req: RunRequest):
    """Analyze coverage gaps between provided documents only"""
    t0 = time.time()
    documents_list = [req.documents] if isinstance(req.documents, str) else req.documents
    
    if len(documents_list) < 2:
        raise HTTPException(
            status_code=400, 
            detail="Need at least 2 document URLs for gap analysis"
        )
    
    # Process only provided documents
    all_clauses = []
    for i, url in enumerate(documents_list):
        doc_id = f"policy_{i+1}_{uuid.uuid4().hex[:8]}"
        fp = await download_blob(url)
        raw = extract_text(fp)
        clauses = chunk(raw, doc_id)
        all_clauses.extend(clauses)
    
    gap_analysis = policy_analyzer.find_coverage_gaps(all_clauses)
    
    return {
        "gap_analysis": gap_analysis,
        "processing_time_ms": int((time.time() - t0) * 1000)
    }


@app.get("/api/v1/system/health", dependencies=[Depends(auth)])
async def system_health():
    """System health check - no local policies"""
    try:
        # Test vector store
        if hasattr(vector_store, 'clauses'):
            vector_status = f"{len(vector_store.clauses)} clauses indexed"
        else:
            collection_stats = vector_store.get_collection_stats()
            vector_status = f"{collection_stats.get('total_points', 0)} points indexed"
        
        return {
            "status": "operational",
            "components": {
                "vector_store": vector_status,
                "llm_service": "openrouter_gpt4o_mini_connected",
                "document_processor": "remote_pdf_supported",
                "authentication": "bearer_token_active"
            },
            "demo_ready": True,
            "local_policies": "disabled",  # Clear indication
            "timestamp": time.time()
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "demo_ready": False,
            "timestamp": time.time()
        }


