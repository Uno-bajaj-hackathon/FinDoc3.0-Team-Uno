"""
Complete Qdrant Cloud vector store implementation with Hugging Face Inference API (Direct HTTP)
✓ Cloud cluster connection with proper error handling
✓ Collection management and indexing
✓ Semantic search with metadata filtering
✓ Clause storage and retrieval with scores
✓ Direct HTTP requests to HF Inference API (most reliable approach)
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from typing import List, Tuple, Optional, Dict, Any
import uuid
import numpy as np
import os
import requests
import json
from app.config import settings
from app.ingestion import Clause

class QdrantVectorStore:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """Initialize Qdrant cloud connection and Hugging Face Inference API"""
        try:
            # Initialize Hugging Face Inference API settings
            self.model_name = model_name
            self.hf_api_url = f"https://api-inference.huggingface.co/models/{model_name}"
            self.hf_headers = {
                "Authorization": f"Bearer {os.environ.get('HF_TOKEN') or settings.huggingface_token}",
                "Content-Type": "application/json"
            }
            
            # Set dimension based on model
            model_dimensions = {
                "sentence-transformers/all-MiniLM-L6-v2": 384,
                "sentence-transformers/all-mpnet-base-v2": 768,
                "sentence-transformers/paraphrase-albert-small-v2": 768,
                "BAAI/bge-small-en-v1.5": 384,
                "BAAI/bge-base-en-v1.5": 768
            }
            self.dimension = model_dimensions.get(model_name, 384)
            
            # Connect to Qdrant Cloud
            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                timeout=30,
                prefer_grpc=False  # Use HTTP REST API
            )
            
            self.collection_name = "insurance_policies"
            
            # Ensure collection exists
            self._ensure_collection_exists()
            print(f"✅ Qdrant Cloud connected successfully to {settings.qdrant_url}")
            print(f"✅ Using Hugging Face Inference API with model: {model_name}")
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            raise e

    def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using direct HTTP requests to HF Inference API"""
        try:
            embeddings = []
            
            for text in texts:
                # Make direct HTTP request to HF Inference API
                response = requests.post(
                    self.hf_api_url,
                    headers=self.hf_headers,
                    json={
                        "inputs": text,
                        "options": {
                            "wait_for_model": True,
                            "use_cache": True
                        }
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    embedding_result = response.json()
                    
                    # Handle different response formats from HF API
                    if isinstance(embedding_result, list):
                        # Check if it's token-level embeddings (2D array)
                        if isinstance(embedding_result[0], list):
                            # Take mean pooling for sentence-level embedding
                            embedding = np.mean(embedding_result, axis=0).tolist()
                        else:
                            # Already sentence-level embedding
                            embedding = embedding_result
                    else:
                        embedding = embedding_result
                    
                    embeddings.append(embedding)
                    
                elif response.status_code == 503:
                    # Model is loading, wait and retry
                    print("⏳ Model loading, waiting 10 seconds...")
                    import time
                    time.sleep(10)
                    return self._generate_embeddings(texts)  # Retry
                    
                else:
                    print(f"⚠️ HF API error {response.status_code}: {response.text}")
                    # Use zero vector as fallback
                    embeddings.append([0.0] * self.dimension)
            
            print(f"✅ Generated {len(embeddings)} embeddings using HF Inference API")
            return embeddings
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error generating embeddings: {e}")
            raise e
        except Exception as e:
            print(f"❌ Error generating embeddings: {e}")
            raise e

    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist"""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                print(f"Creating collection '{self.collection_name}'...")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.dimension,
                        distance=Distance.COSINE
                    )
                )
                print(f"✅ Collection '{self.collection_name}' created")
            else:
                # Get collection info
                collection_info = self.client.get_collection(self.collection_name)
                print(f"✅ Collection '{self.collection_name}' exists with {collection_info.points_count} points")
                
        except Exception as e:
            print(f"❌ Collection setup failed: {e}")
            raise e

    def add_clauses(self, clauses: List[Clause]) -> int:
        """Add clause embeddings to Qdrant with metadata using HF Inference API"""
        if not clauses:
            return 0
        
        try:
            # Generate embeddings for all clauses using HF Inference API
            texts = [clause.text for clause in clauses]
            embeddings = self._generate_embeddings(texts)
            
            # Create points for Qdrant
            points = []
            for clause, embedding in zip(clauses, embeddings):
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,  # HF embeddings are typically normalized
                    payload={
                        "clause_id": clause.id,
                        "text": clause.text,
                        "doc_id": clause.id.split('_')[0],  # Extract document ID
                        "chunk_index": int(clause.id.split('_c')[1]) if '_c' in clause.id else 0
                    }
                )
                points.append(point)
            
            # Batch upsert to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            print(f"✅ Added {len(clauses)} clauses to Qdrant using HF Inference API")
            return len(clauses)
            
        except Exception as e:
            print(f"❌ Failed to add clauses: {e}")
            raise e

    def search(self, query: str, k: int = 5, doc_filter: Optional[str] = None) -> List[Tuple[Clause, float, Dict[str, Any]]]:
        """
        Semantic search with optional document filtering using HF Inference API
        Returns: List of (Clause, similarity_score, metadata) tuples
        """
        try:
            # Generate query embedding using HF Inference API
            query_embeddings = self._generate_embeddings([query])
            query_embedding = query_embeddings[0]
            
            # Build filter if specified
            query_filter = None
            if doc_filter:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_filter)
                        )
                    ]
                )
            
            # Search in Qdrant
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=k,
                with_payload=True,
                query_filter=query_filter
            )
            
            # Convert results to Clause objects
            results = []
            for hit in search_results:
                # Reconstruct Clause object
                clause = Clause(
                    doc_id=hit.payload["doc_id"],
                    idx=hit.payload["chunk_index"],
                    text=hit.payload["text"]
                )
                
                clause.id = hit.payload["clause_id"]  # Override with stored ID
                
                # Add metadata
                metadata = {
                    "point_id": hit.id,
                    "doc_id": hit.payload["doc_id"],
                    "chunk_index": hit.payload["chunk_index"]
                }
                
                results.append((clause, hit.score, metadata))
            
            print(f"🔍 Found {len(results)} relevant clauses for query: '{query[:50]}...'")
            return results
            
        except Exception as e:
            print(f"❌ Search failed: {e}")
            return []

    def search_by_document(self, doc_id: str, limit: int = 10) -> List[Tuple[Clause, Dict[str, Any]]]:
        """Get all clauses from a specific document"""
        try:
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id)
                        )
                    ]
                ),
                limit=limit,
                with_payload=True
            )
            
            clauses = []
            for point in results[0]:
                clause = Clause(
                    doc_id=point.payload["doc_id"],
                    idx=point.payload["chunk_index"],
                    text=point.payload["text"]
                )
                
                clause.id = point.payload["clause_id"]
                metadata = {
                    "point_id": point.id,
                    "chunk_index": point.payload["chunk_index"]
                }
                
                clauses.append((clause, metadata))
            
            return clauses
            
        except Exception as e:
            print(f"❌ Document search failed: {e}")
            return []

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics and health info"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "collection_name": self.collection_name,
                "total_points": collection_info.points_count,
                "vector_dimension": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.value,
                "status": collection_info.status.value,
                "optimizer_status": collection_info.optimizer_status.ok if collection_info.optimizer_status else "unknown",
                "embedding_model": self.model_name
            }
        except Exception as e:
            return {"error": str(e)}

    def clear_collection(self) -> bool:
        """Clear all points from the collection (useful for testing)"""
        try:
            all_points = self.client.scroll(
                collection_name=self.collection_name,
                limit=10000,
                with_payload=False
            )
            
            if all_points[0]:
                point_ids = [point.id for point in all_points[0]]
                self.client.delete(
                    collection_name=self.collection_name,
                    points_selector=point_ids
                )
                print(f"✅ Cleared {len(point_ids)} points from collection")
                return True
                
            print("✅ Collection already empty")
            return True
            
        except Exception as e:
            print(f"❌ Failed to clear collection: {e}")
            return False

    def delete_by_document(self, doc_id: str) -> int:
        """Delete all clauses from a specific document"""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="doc_id",
                            match=MatchValue(value=doc_id)
                        )
                    ]
                )
            )
            print(f"✅ Deleted all clauses from document: {doc_id}")
            return 1
        except Exception as e:
            print(f"❌ Failed to delete document: {e}")
            return 0

    def hybrid_search(self, query: str, keywords: List[str], k: int = 5) -> List[Tuple[Clause, float, Dict[str, Any]]]:
        """Combine semantic search with keyword filtering"""
        try:
            semantic_results = self.search(query, k=k*2)
            
            if keywords:
                filtered_results = []
                for clause, score, metadata in semantic_results:
                    clause_text_lower = clause.text.lower()
                    if any(keyword.lower() in clause_text_lower for keyword in keywords):
                        filtered_results.append((clause, score * 1.1, metadata))
                    else:
                        filtered_results.append((clause, score, metadata))
                
                filtered_results.sort(key=lambda x: x[1], reverse=True)
                return filtered_results[:k]
                
            return semantic_results[:k]
            
        except Exception as e:
            print(f"❌ Hybrid search failed: {e}")
            return []

# Global instance (initialized in main.py)
vector_store: Optional[QdrantVectorStore] = None

def get_vector_store() -> QdrantVectorStore:
    """Get the global vector store instance"""
    global vector_store
    if vector_store is None:
        vector_store = QdrantVectorStore()
    return vector_store
