# Vector Store Service with LiteLLM Integration

This service provides a comprehensive solution for managing vector embeddings and vector stores, fully integrated with LiteLLM for embedding generation and using Pinecone as the vector store backend.

## 🚀 Features

- **Pinecone Vector Store**: Cloud-based vector database with high performance and scalability
- **LiteLLM Integration**: Uses LiteLLM for embedding generation with any supported model
- **Metadata Support**: Rich metadata filtering and storage
- **Observability**: Langfuse integration for monitoring and tracing
- **Error Handling**: Robust error handling with fallbacks

## 📦 Installation

The required packages are already installed:

```bash
pip install pinecone-client
```

## 🔧 Configuration

### Environment Variables

Add these to your configuration:

```python
# In config.py
EMBEDDING_MODEL = "text-embedding-3-small"  # or any LiteLLM supported model
KNN_EMBEDDING_DIMENSION = 1536  # Must match your embedding model
PINECONE_API_KEY = "your-pinecone-api-key"
PINECONE_ENVIRONMENT = "gcp-starter"  # or your Pinecone environment
PINECONE_INDEX_NAME = "db-schema"  # your Pinecone index name
```

### Supported Embedding Models

The service supports all LiteLLM embedding models:

- **OpenAI**: `text-embedding-3-small`, `text-embedding-3-large`
- **Cohere**: `cohere.embed-english-v3`
- **Amazon**: `amazon.titan-embed-text-v2:0`
- **HuggingFace**: Any sentence-transformers model

## 🎯 Usage Examples

### Basic Usage

```python
from app.services.vector_store.vector_store_service import VectorStoreService

# Initialize with default settings
vector_store = VectorStoreService()

# Add documents
documents = [
    "The quick brown fox jumps over the lazy dog.",
    "Machine learning is a subset of artificial intelligence.",
    "Vector databases store high-dimensional data efficiently."
]

metadata = [
    {"category": "animals", "source": "literature"},
    {"category": "technology", "source": "academic"},
    {"category": "technology", "source": "technical"}
]

# Add documents to vector store
doc_ids = vector_store.add_documents(documents, metadata)

# Search for similar documents
results = vector_store.search("What is machine learning?", n_results=3)

for result in results:
    print(f"Document: {result['document']}")
    print(f"Score: {result['score']:.3f}")
    print(f"Metadata: {result['metadata']}")
    print("---")
```

### Custom Configuration

```python
# Custom namespace and index
vector_store = VectorStoreService(
    collection_name="my_namespace",
    index_name="my-index"
)

# Custom embedding model
vector_store = VectorStoreService(
    embedding_model="text-embedding-3-large"
)
```

### Advanced Usage

#### Metadata Filtering

```python
# Search with metadata filters
results = vector_store.search(
    query="machine learning",
    n_results=5,
    filter_metadata={"category": "technology"}
)
```

#### Batch Operations

```python
# Add large batches of documents
large_documents = [
    f"Document {i}: This is sample content for document number {i}."
    for i in range(1000)
]

large_metadata = [
    {"batch": "large", "index": i}
    for i in range(1000)
]

doc_ids = vector_store.add_documents(large_documents, large_metadata)
```

## 🔍 Search and Retrieval

### Similarity Search

```python
# Basic similarity search
results = vector_store.search("query text", n_results=5)

# Search with filters
results = vector_store.search(
    query="query text",
    n_results=10,
    filter_metadata={"category": "technology", "source": "academic"}
)
```

### Collection Management

```python
# Get collection information
info = vector_store.get_collection_info()
print(f"Index: {info['index_name']}")
print(f"Namespace: {info['namespace']}")
print(f"Document count: {info['count']}")
print(f"Embedding model: {info['embedding_model']}")
print(f"Dimensions: {info['embedding_dimensions']}")

# Delete collection (namespace)
vector_store.delete_collection()
```

## 🏗️ Architecture

### Integration with LiteLLM

The service uses LiteLLM's `embedding()` function for generating embeddings:

```python
from litellm import embedding

# This is handled internally by the service
response = embedding(
    model="text-embedding-3-small",
    input="Your text here"
)
```

### Pinecone Backend

**Pros:**
- Cloud-based with high availability
- Automatic scaling
- Built-in metadata filtering
- Production-ready
- Fast similarity search
- Global distribution

**Best for:** Production applications, high-scale deployments, cloud-native architectures

## 🔧 Integration with Existing Code

### Adding to Your Application

```python
# In your command or service
from app.services.vector_store.vector_store_service import VectorStoreService

class YourCommand:
    def __init__(self):
        self.vector_store = VectorStoreService()
    
    def process_documents(self, documents):
        # Add documents to vector store
        doc_ids = self.vector_store.add_documents(documents)
        
        # Later, search for similar documents
        results = self.vector_store.search("your query")
        return results
```

### RAG (Retrieval-Augmented Generation)

```python
# Example RAG implementation
def rag_query(query: str, context_documents: List[str]):
    # Add context documents to vector store
    vector_store = VectorStoreService()
    vector_store.add_documents(context_documents)
    
    # Retrieve relevant documents
    results = vector_store.search(query, n_results=3)
    
    # Build context for LLM
    context = "\n".join([r['document'] for r in results])
    
    # Use with your LLM session
    llm_session = LLMSession()
    response = llm_session.chat([
        {"role": "system", "content": f"Context: {context}"},
        {"role": "user", "content": query}
    ])
    
    return response
```

## 📊 Performance Considerations

### Embedding Generation
- **Batch Processing**: Generate embeddings in batches for better performance
- **Caching**: Consider caching embeddings for frequently accessed documents
- **Model Selection**: Choose embedding models based on your use case

### Pinecone Performance
- **Scalability**: Handles millions of vectors efficiently
- **Query Speed**: Fast similarity search with optimized indexes
- **Availability**: 99.9% uptime SLA
- **Global Distribution**: Low-latency access from multiple regions

## 🐛 Troubleshooting

### Common Issues

1. **API Key Issues**
   ```python
   # Ensure PINECONE_API_KEY is set in environment
   import os
   print(os.environ.get("PINECONE_API_KEY"))
   ```

2. **Index Not Found**
   ```python
   # Check if index exists
   import pinecone
   pinecone.init(api_key="your-key", environment="your-env")
   print(pinecone.list_indexes())
   ```

3. **Dimension Mismatch**
   ```python
   # Ensure KNN_EMBEDDING_DIMENSION matches your model
   # text-embedding-3-small: 1536
   # text-embedding-3-large: 3072
   # cohere.embed-english-v3: 1024
   ```

### Debugging

```python
# Enable debug logging
import logging
logging.getLogger('app.services.vector_store').setLevel(logging.DEBUG)

# Check collection info
info = vector_store.get_collection_info()
print(info)
```

## 🔗 Related Documentation

- [LiteLLM Documentation](https://docs.litellm.ai/)
- [Pinecone Documentation](https://docs.pinecone.io/)

## 📝 Example Use Cases

1. **Document Search**: Find similar documents in a knowledge base
2. **Semantic Search**: Search by meaning rather than keywords
3. **Recommendation Systems**: Find similar items or content
4. **RAG Applications**: Retrieve relevant context for LLM queries
5. **Duplicate Detection**: Find similar or duplicate content
6. **Content Clustering**: Group similar documents together
