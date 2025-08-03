# app/dataset_loader.py
import os
from pathlib import Path
from typing import List
from .ingestion import extract_text, chunk, Clause

class PolicyDatasetLoader:
    def __init__(self, dataset_path: str = "datasets/policies"):
        self.dataset_path = Path(dataset_path)
        
    def load_sample_policies(self) -> List[Clause]:
        """Load all sample policies from local directory"""
        all_clauses = []
        
        for policy_file in self.dataset_path.glob("*.pdf"):
            doc_id = policy_file.stem  # Use filename as doc_id
            raw_text = extract_text(policy_file)
            clauses = chunk(raw_text, doc_id)
            all_clauses.extend(clauses)
            print(f"Loaded {len(clauses)} clauses from {policy_file.name}")
            
        return all_clauses
