import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any
from pathlib import Path
from utils.chunking import chunk_text
from config import get_settings


class VectorStore:
    def __init__(self, embedding_service):
        self.embedding_service = embedding_service
        self.settings = get_settings()
        
        # Initialize ChromaDB
        db_path = Path(self.settings.VECTOR_DB_PATH)
        db_path.mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=str(db_path),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        try:
            self.collection = self.client.get_collection(self.settings.COLLECTION_NAME)
        except:
            self.collection = self.client.create_collection(
                name=self.settings.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
    
    def build_from_documents(self, documents: List[Dict[str, Any]]) -> int:
        """Build vector store from documents"""
        all_chunks = []
        all_metadata = []
        
        for doc in documents:
            # Chunk document
            chunks = chunk_text(
                doc['content'],
                chunk_size=self.settings.CHUNK_SIZE,
                overlap=self.settings.CHUNK_OVERLAP
            )
            
            # Prepare metadata
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                all_metadata.append({
                    'source': doc['source'],
                    'type': doc['type'],
                    'chunk_index': i,
                    'total_chunks': len(chunks)
                })
        
        # Generate embeddings
        embeddings = self.embedding_service.generate_embeddings(all_chunks)
        
        # Store in vector DB
        ids = [f"doc_{i}" for i in range(len(all_chunks))]
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=all_chunks,
            metadatas=all_metadata
        )
        
        return len(all_chunks)
    
    def query(self, query_text: str, k: int = 5) -> List[Dict[str, Any]]:
        """Query vector store"""
        # Generate query embedding
        query_embedding = self.embedding_service.generate_embedding(query_text)
        
        # Query collection
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )
        
        # Format results
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                'content': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i] if 'distances' in results else None
            })
        
        return formatted_results
    
    def is_initialized(self) -> bool:
        """Check if collection has documents"""
        return self.collection.count() > 0
    
    def get_document_count(self) -> int:
        """Get total document count"""
        return self.collection.count()
    
    def reset(self):
        """Reset collection"""
        self.client.delete_collection(self.settings.COLLECTION_NAME)
        self.collection = self.client.create_collection(
            name=self.settings.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
