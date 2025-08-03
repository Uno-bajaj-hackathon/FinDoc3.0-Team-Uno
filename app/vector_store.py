"""
Complete Qdrant Cloud vector store implementation
✓ Cloud cluster connection with proper error handling
✓ Collection management and indexing
✓ Semantic search with metadata filtering
✓ Clause storage and retrieval with scores
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from typing import List, Tuple, Optional, Dict, Any
import uuid
import numpy as np
from app.config import settings
from app.ingestion import Clause

class QdrantVectorStore:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize Qdrant cloud connection and embedding model"""
        try:
            # Initialize embedding model
            self.model = SentenceTransformer(model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            
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
            
        except Exception as e:
            print(f"❌ Qdrant connection failed: {e}")
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
        """Add clause embeddings to Qdrant with metadata"""
        if not clauses:
            return 0
        
        try:
            # Generate embeddings for all clauses
            texts = [clause.text for clause in clauses]
            embeddings = self.model.encode(texts, normalize_embeddings=True)
            
            # Create points for Qdrant
            points = []
            for clause, embedding in zip(clauses, embeddings):
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding.tolist(),
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
            
            print(f"✅ Added {len(clauses)} clauses to Qdrant")
            return len(clauses)
            
        except Exception as e:
            print(f"❌ Failed to add clauses: {e}")
            raise e
    
    def search(self, query: str, k: int = 5, doc_filter: Optional[str] = None) -> List[Tuple[Clause, float, Dict[str, Any]]]:
        """
        Semantic search with optional document filtering
        Returns: List of (Clause, similarity_score, metadata) tuples
        """
        try:
            # Generate query embedding
            query_embedding = self.model.encode([query], normalize_embeddings=True)[0]
            
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
                query_vector=query_embedding.tolist(),
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
            # Search with document filter
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
            for point in results[0]:  # results is (points, next_page_offset)
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
                "optimizer_status": collection_info.optimizer_status.ok if collection_info.optimizer_status else "unknown"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def clear_collection(self) -> bool:
        """Clear all points from the collection (useful for testing)"""
        try:
            # Get all points and delete them
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
            # Delete points with matching doc_id
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
        """
        Combine semantic search with keyword filtering
        Useful for insurance domain-specific searches
        """
        try:
            # First do semantic search
            semantic_results = self.search(query, k=k*2)  # Get more results initially
            
            # Filter results that contain any of the keywords
            if keywords:
                filtered_results = []
                for clause, score, metadata in semantic_results:
                    clause_text_lower = clause.text.lower()
                    if any(keyword.lower() in clause_text_lower for keyword in keywords):
                        filtered_results.append((clause, score * 1.1, metadata))  # Boost score
                    else:
                        filtered_results.append((clause, score, metadata))
                
                # Sort by boosted scores and return top k
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
