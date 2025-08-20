from typing import List, Dict, Any, Optional
from flask import current_app
import uuid

from app import logger
from app.services.llm.session import LLMSession

# Vector store imports
from pinecone import Pinecone, ServerlessSpec

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
        self.namespace = collection_name or "default"  # Use collection_name instead of hardcoded "dbschema"
        self.index_name = index_name or current_app.config.get("PINECONE_INDEX_NAME", "dbschema")
        
        # Initialize LLM session for embeddings
        self.llm_session = LLMSession(embedding_model=self.embedding_model)
        
        # Initialize Pinecone
        self._init_pinecone()
    
    def _init_pinecone(self):
        """Initialize Pinecone vector store."""
        try:
            # Get Pinecone configuration
            api_key = current_app.config.get("PINECONE_API_KEY")
            
            if not api_key:
                logger.warning("PINECONE_API_KEY not found in configuration - vector store will be disabled")
                self.pc = None
                self.index = None
                return
            
            # Initialize Pinecone client
            self.pc = Pinecone(api_key=api_key)
            
            # Get embedding dimensions
            embedding_dimensions = getattr(self.llm_session, 'knn_embedding_dimensions', 1536)
            
            # Check if index exists, create if it doesn't
            try:
                existing_indexes = self.pc.list_indexes()
                index_names = [idx.name for idx in existing_indexes]
                
                if self.index_name not in index_names:
                    logger.info(f"Creating Pinecone index: {self.index_name}")
                    self.pc.create_index(
                        name=self.index_name,
                        dimension=embedding_dimensions,
                        metric="cosine",
                        spec=ServerlessSpec(
                            cloud="aws",
                            region="us-east-1"
                        )
                    )
                    # Wait for index to be ready
                    import time
                    time.sleep(10)
                    
            except Exception as e:
                logger.warning(f"Index creation failed: {e}")
                # Continue with existing index if creation fails
            
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
        # Check if Pinecone is initialized
        if not self.pc or not self.index:
            logger.warning("Pinecone not initialized - cannot add documents")
            return []
            
        if not documents:
            return []
        
        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(documents))]
        
        try:
            # Generate embeddings for all documents
            embeddings = self.llm_session.get_embeddings(documents)
            
            # Prepare vectors for upsert
            vectors_to_upsert = []
            for i, (doc_id, document, embedding) in enumerate(zip(ids, documents, embeddings)):
                # Prepare metadata
                doc_metadata = {"chunk_text": document}
                if metadata and i < len(metadata):
                    doc_metadata.update(metadata[i])
                
                vector_data = {
                    "id": doc_id,
                    "values": embedding,
                    "metadata": doc_metadata
                }
                vectors_to_upsert.append(vector_data)
            
            # Upsert vectors to Pinecone
            self.index.upsert(
                vectors=vectors_to_upsert,
                namespace=self.namespace
            )
            
            logger.info(f"Added {len(documents)} documents to Pinecone index: {self.index_name}, namespace: {self.namespace}")
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
        # Check if Pinecone is initialized
        if not self.pc or not self.index:
            logger.warning("Pinecone not initialized - returning empty results")
            return []
        
        try:
            # Generate query embedding
            query_embeddings = self.llm_session.get_embeddings([query])
            if not query_embeddings:
                logger.error("Failed to generate query embedding")
                return []
            
            query_embedding = query_embeddings[0]
            
            # Prepare query parameters
            query_params = {
                "vector": query_embedding,
                "top_k": n_results,
                "namespace": self.namespace,
                "include_metadata": True
            }
            
            # Add filter if provided
            if filter_metadata:
                query_params["filter"] = filter_metadata
            
            logger.info(f"Searching namespace: {self.namespace}, index: {self.index_name}")
            
            # Search in Pinecone
            results = self.index.query(**query_params)
            
            # Format results
            formatted_results = []
            for match in results.get('matches', []):
                formatted_results.append({
                    "document": match['metadata'].get('chunk_text', ''),
                    "metadata": {k: v for k, v in match['metadata'].items() if k != 'chunk_text'},
                    "score": match['score'],
                    "id": match['id']
                })
            
            logger.info(f"Found {len(formatted_results)} results for query")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
            
    def delete_collection(self):
        """Delete the current namespace (collection)."""
        if not self.pc or not self.index:
            logger.warning("Pinecone not initialized - cannot delete collection")
            return
            
        try:
            # Delete all vectors in the namespace
            self.index.delete(delete_all=True, namespace=self.namespace)
            logger.info(f"Deleted all vectors from Pinecone namespace: {self.namespace}")
                
        except Exception as e:
            logger.error(f"Failed to delete namespace: {e}")
            raise
    
    def delete_documents(self, ids: List[str]):
        """Delete specific documents by their IDs."""
        if not self.pc or not self.index:
            logger.warning("Pinecone not initialized - cannot delete documents")
            return
            
        try:
            self.index.delete(ids=ids, namespace=self.namespace)
            logger.info(f"Deleted {len(ids)} documents from namespace: {self.namespace}")
        except Exception as e:
            logger.error(f"Failed to delete documents: {e}")
            raise
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the current collection."""
        if not self.pc or not self.index:
            return {"error": "Pinecone not initialized"}
            
        try:
            stats = self.index.describe_index_stats()
            namespace_stats = stats.get('namespaces', {}).get(self.namespace, {})
            
            # Get embedding dimensions from LLM session
            embedding_dimensions = getattr(self.llm_session, 'knn_embedding_dimensions', 'unknown')
            
            info = {
                "vector_store_type": "pinecone",
                "index_name": self.index_name,
                "namespace": self.namespace,
                "embedding_model": self.embedding_model,
                "embedding_dimensions": embedding_dimensions,
                "total_vector_count": stats.get('total_vector_count', 0),
                "namespace_vector_count": namespace_stats.get('vector_count', 0),
                "index_fullness": stats.get('index_fullness', 0)
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {"error": str(e)}
    
    
    
    def update_document(self, doc_id: str, document: str, metadata: Optional[Dict[str, Any]] = None):
        """Update a specific document."""
        if not self.pc or not self.index:
            logger.warning("Pinecone not initialized - cannot update document")
            return
            
        try:
            # Generate new embedding
            embedding = self.llm_session.get_embeddings([document])[0]
            
            # Prepare metadata
            doc_metadata = {"chunk_text": document}
            if metadata:
                doc_metadata.update(metadata)
            
            # Update the vector
            self.index.upsert(
                vectors=[{
                    "id": doc_id,
                    "values": embedding,
                    "metadata": doc_metadata
                }],
                namespace=self.namespace
            )
            
            logger.info(f"Updated document {doc_id} in namespace: {self.namespace}")
            
        except Exception as e:
            logger.error(f"Failed to update document {doc_id}: {e}")
            raise