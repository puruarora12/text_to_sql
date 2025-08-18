from typing import List, Dict, Any, Optional
from flask import current_app

from app import logger
from app.services.llm.session import LLMSession

# Vector store imports
from pinecone import Pinecone

from langfuse.decorators import observe


class VectorStoreService:
    """
    A service for managing vector embeddings and vector stores.
    Uses Pinecone with integrated embedding models for automatic vector generation.
    """
    
    def __init__(
        self,
        embedding_model: str = None,
        collection_name: str = "default",
        index_name: str = None
    ):
        """
        Initialize the vector store service.
        
        Args:
            embedding_model: The embedding model to use (defaults to config)
            collection_name: Name of the collection/namespace (used as namespace in Pinecone)
            index_name: Name of the Pinecone index (defaults to config)
        """
        self.embedding_model = embedding_model or current_app.config.get("EMBEDDING_MODEL", "text-embedding-3-small")
        self.namespace = collection_name
        self.index_name = index_name or current_app.config.get("PINECONE_INDEX_NAME", "dbschema")
        
        # Initialize LLM session for embeddings (fallback)
        self.llm_session = LLMSession(embedding_model=self.embedding_model)
        
        # Initialize Pinecone
        self._init_pinecone()
    
    def _init_pinecone(self):
        """Initialize Pinecone vector store."""
        try:
            # Get Pinecone configuration
            api_key = current_app.config.get("PINECONE_API_KEY")
            
            if not api_key:
                raise ValueError("PINECONE_API_KEY not found in configuration")
            
            # Initialize Pinecone client
            self.pc = Pinecone(api_key=api_key)
            
            # Check if index exists, create if it doesn't
            if not self.pc.has_index(self.index_name):
                logger.info(f"Creating Pinecone index: {self.index_name}")
                self.pc.create_index_for_model(
                    name=self.index_name,
                    cloud="aws",
                    region="us-east-1",
                    embed={
                        "model": "text-embedding-3-small",
                        "field_map": {"text": "chunk_text"}
                    }
                )
            
            # Connect to the index
            self.index = self.pc.Index(self.index_name)
            logger.info(f"Initialized Pinecone index: {self.index_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")
            raise
    
    @observe()
    def add_documents(
        self,
        documents: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of document texts
            metadata: Optional list of metadata dictionaries
            ids: Optional list of document IDs
            
        Returns:
            List of document IDs
        """
        if not documents:
            return []
        
        # Generate IDs if not provided
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
        
        try:
            # Prepare records for Pinecone
            records = []
            for i, (doc_id, document) in enumerate(zip(ids, documents)):
                record = {
                    "_id": doc_id,
                    "chunk_text": document
                }
                
                # Add custom metadata if provided
                if metadata and i < len(metadata):
                    record.update(metadata[i])
                
                records.append(record)
            
            # Upsert records to Pinecone
            self.index.upsert_records(self.namespace, records)
            logger.info(f"Added {len(documents)} documents to Pinecone index: {self.index_name}")
            return ids
            
        except Exception as e:
            logger.error(f"Failed to add documents to Pinecone: {e}")
            raise
    
    @observe()
    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.
        
        Args:
            query: Search query text
            n_results: Number of results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of search results with documents and scores
        """
        try:
            # Prepare filter for Pinecone
            filter_dict = None
            if filter_metadata:
                filter_dict = {}
                for key, value in filter_metadata.items():
                    filter_dict[key] = {"$eq": value}
            
            # Search in Pinecone
            results = self.index.search(
                namespace=self.namespace,
                query={
                    "top_k": n_results,
                    "inputs": {
                        'text': query
                    }
                },
                filter=filter_dict
            )
            
            # Format results
            formatted_results = []
            for hit in results['result']['hits']:
                formatted_results.append({
                    "document": hit['fields'].get('chunk_text', ''),
                    "metadata": {k: v for k, v in hit['fields'].items() if k != 'chunk_text'},
                    "score": hit['_score']
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to search Pinecone: {e}")
            return []
    
    def delete_collection(self):
        """Delete the current namespace (collection)."""
        try:
            self.index.delete(namespace=self.namespace, delete_all=True)
            logger.info(f"Deleted all vectors from Pinecone namespace: {self.namespace}")
                
        except Exception as e:
            logger.error(f"Failed to delete namespace: {e}")
            raise
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the current collection."""
        try:
            stats = self.index.describe_index_stats()
            namespace_stats = stats.get('namespaces', {}).get(self.namespace, {})
            
            info = {
                "vector_store_type": "pinecone",
                "index_name": self.index_name,
                "namespace": self.namespace,
                "embedding_model": self.embedding_model,
                "embedding_dimensions": self.llm_session.knn_embedding_dimensions,
                "count": namespace_stats.get('vector_count', 0)
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}
