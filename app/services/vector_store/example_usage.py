#!/usr/bin/env python3
"""
Example usage of the VectorStoreService with Pinecone backend.

This script demonstrates various features of the vector store service
including document addition, searching, metadata filtering, and RAG applications.
"""

import os
import sys
from typing import List, Dict, Any

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from app.services.vector_store.vector_store_service import VectorStoreService
from app.services.llm.session import LLMSession


def basic_usage_example():
    """Demonstrate basic vector store operations."""
    print("=== Basic Usage Example ===")
    
    # Initialize vector store
    vector_store = VectorStoreService(
        collection_name="example_namespace",
        index_name="example-index"
    )
    
    # Sample documents
    documents = [
        "The quick brown fox jumps over the lazy dog.",
        "Machine learning is a subset of artificial intelligence.",
        "Vector databases store high-dimensional data efficiently.",
        "Python is a popular programming language for data science.",
        "Natural language processing enables computers to understand human language."
    ]
    
    # Metadata for each document
    metadata = [
        {"category": "animals", "source": "literature", "difficulty": "easy"},
        {"category": "technology", "source": "academic", "difficulty": "medium"},
        {"category": "technology", "source": "technical", "difficulty": "advanced"},
        {"category": "programming", "source": "educational", "difficulty": "beginner"},
        {"category": "technology", "source": "academic", "difficulty": "medium"}
    ]
    
    # Add documents to vector store
    print("Adding documents to vector store...")
    doc_ids = vector_store.add_documents(documents, metadata)
    print(f"Added {len(doc_ids)} documents with IDs: {doc_ids[:3]}...")
    
    # Search for similar documents
    print("\nSearching for 'machine learning'...")
    results = vector_store.search("machine learning", n_results=3)
    
    for i, result in enumerate(results, 1):
        print(f"\nResult {i}:")
        print(f"  Document: {result['document'][:100]}...")
        print(f"  Score: {result['score']:.3f}")
        print(f"  Metadata: {result['metadata']}")
    
    # Get collection information
    print("\nCollection Information:")
    info = vector_store.get_collection_info()
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    return vector_store


def metadata_filtering_example(vector_store: VectorStoreService):
    """Demonstrate metadata filtering capabilities."""
    print("\n=== Metadata Filtering Example ===")
    
    # Search with category filter
    print("Searching for 'technology' documents...")
    results = vector_store.search(
        query="data science",
        n_results=5,
        filter_metadata={"category": "technology"}
    )
    
    print(f"Found {len(results)} technology documents:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result['document'][:80]}... (Score: {result['score']:.3f})")
    
    # Search with multiple filters
    print("\nSearching for 'academic' documents with 'medium' difficulty...")
    results = vector_store.search(
        query="artificial intelligence",
        n_results=3,
        filter_metadata={"source": "academic", "difficulty": "medium"}
    )
    
    print(f"Found {len(results)} academic medium-difficulty documents:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result['document'][:80]}... (Score: {result['score']:.3f})")


def batch_operations_example():
    """Demonstrate batch operations with large datasets."""
    print("\n=== Batch Operations Example ===")
    
    # Create a new vector store for batch operations
    batch_store = VectorStoreService(
        collection_name="batch_example",
        index_name="batch-index"
    )
    
    # Generate large batch of documents
    large_documents = []
    large_metadata = []
    
    for i in range(100):
        doc = f"Document {i}: This is sample content for document number {i}. "
        doc += f"It contains information about topic {i % 10} and category {i % 5}."
        
        large_documents.append(doc)
        large_metadata.append({
            "document_id": i,
            "topic": i % 10,
            "category": i % 5,
            "batch": "large_operation"
        })
    
    print(f"Adding {len(large_documents)} documents in batch...")
    doc_ids = batch_store.add_documents(large_documents, large_metadata)
    print(f"Successfully added {len(doc_ids)} documents")
    
    # Search in large dataset
    print("\nSearching in large dataset...")
    results = batch_store.search("topic 5", n_results=5)
    
    print(f"Found {len(results)} relevant documents:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result['document'][:60]}... (Score: {result['score']:.3f})")
    
    # Get collection stats
    info = batch_store.get_collection_info()
    print(f"\nBatch collection stats: {info['count']} documents")
    
    return batch_store


def rag_application_example(vector_store: VectorStoreService):
    """Demonstrate RAG (Retrieval-Augmented Generation) application."""
    print("\n=== RAG Application Example ===")
    
    # Initialize LLM session
    llm_session = LLMSession()
    
    # User query
    user_query = "What is machine learning and how does it relate to artificial intelligence?"
    
    print(f"User Query: {user_query}")
    
    # Retrieve relevant documents
    print("\nRetrieving relevant documents...")
    results = vector_store.search(user_query, n_results=3)
    
    # Build context from retrieved documents
    context_documents = [result['document'] for result in results]
    context = "\n\n".join(context_documents)
    
    print(f"\nRetrieved Context:")
    for i, doc in enumerate(context_documents, 1):
        print(f"  {i}. {doc[:100]}...")
    
    # Create RAG prompt
    rag_prompt = f"""Based on the following context, answer the user's question:

Context:
{context}

Question: {user_query}

Answer:"""
    
    print(f"\nRAG Prompt:")
    print(rag_prompt[:200] + "...")
    
    # In a real application, you would send this to your LLM
    print("\n[In a real application, this would be sent to the LLM for generation]")
    print("The LLM would generate a comprehensive answer based on the retrieved context.")
    
    # Simulate LLM response
    print("\nSimulated LLM Response:")
    print("Based on the retrieved context, machine learning is a subset of artificial intelligence")
    print("that enables computers to learn and improve from experience without being explicitly programmed.")
    print("It focuses on developing algorithms that can access data and use it to learn for themselves.")


def collection_management_example():
    """Demonstrate collection management operations."""
    print("\n=== Collection Management Example ===")
    
    # Create a temporary collection
    temp_store = VectorStoreService(
        collection_name="temp_collection",
        index_name="temp-index"
    )
    
    # Add some test documents
    test_docs = ["Test document 1", "Test document 2", "Test document 3"]
    temp_store.add_documents(test_docs)
    
    # Get collection info
    info = temp_store.get_collection_info()
    print(f"Created temporary collection with {info['count']} documents")
    
    # Search in temporary collection
    results = temp_store.search("test", n_results=2)
    print(f"Found {len(results)} test documents")
    
    # Delete the collection
    print("Deleting temporary collection...")
    temp_store.delete_collection()
    print("Temporary collection deleted")
    
    # Note: In Pinecone, this deletes all vectors in the namespace
    # The index itself remains but is empty for this namespace


def performance_comparison_example():
    """Demonstrate performance characteristics."""
    print("\n=== Performance Comparison Example ===")
    
    # Create performance test store
    perf_store = VectorStoreService(
        collection_name="performance_test",
        index_name="perf-index"
    )
    
    # Test different embedding models
    embedding_models = ["text-embedding-3-small", "text-embedding-3-large"]
    
    for model in embedding_models:
        print(f"\nTesting with {model}:")
        
        # Create store with specific model
        test_store = VectorStoreService(
            embedding_model=model,
            collection_name=f"test_{model.replace('-', '_')}",
            index_name="test-index"
        )
        
        # Add test documents
        test_docs = [
            "Performance test document for embedding model comparison.",
            "This document will be used to test different embedding models.",
            "We'll compare the performance and quality of different models."
        ]
        
        test_store.add_documents(test_docs)
        
        # Search and measure performance
        results = test_store.search("performance test", n_results=2)
        
        print(f"  - Added {len(test_docs)} documents")
        print(f"  - Found {len(results)} results")
        print(f"  - Top result score: {results[0]['score']:.3f}")
        
        # Clean up
        test_store.delete_collection()


def main():
    """Run all examples."""
    print("Vector Store Service Examples with Pinecone Backend")
    print("=" * 60)
    
    try:
        # Basic usage
        vector_store = basic_usage_example()
        
        # Metadata filtering
        metadata_filtering_example(vector_store)
        
        # Batch operations
        batch_store = batch_operations_example()
        
        # RAG application
        rag_application_example(vector_store)
        
        # Collection management
        collection_management_example()
        
        # Performance comparison
        performance_comparison_example()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("\nKey Features Demonstrated:")
        print("✅ Basic document addition and search")
        print("✅ Metadata filtering and querying")
        print("✅ Batch operations with large datasets")
        print("✅ RAG application workflow")
        print("✅ Collection management operations")
        print("✅ Performance testing with different models")
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        print("Make sure you have:")
        print("1. Set PINECONE_API_KEY in your environment")
        print("2. Set PINECONE_ENVIRONMENT in your environment")
        print("3. Installed pinecone-client: pip install pinecone-client")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
