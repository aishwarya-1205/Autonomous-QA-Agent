from typing import List, Dict, Any


class RAGService:
    def __init__(self, vector_store, embedding_service):
        self.vector_store = vector_store
        self.embedding_service = embedding_service
    
    def retrieve_context(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant context for a query"""
        results = self.vector_store.query(query, k=k)
        return results
    
    def format_context(self, results: List[Dict[str, Any]]) -> str:
        """Format retrieved results into context string"""
        context_parts = []
        
        for i, result in enumerate(results, 1):
            source = result['metadata'].get('source', 'unknown')
            content = result['content']
            context_parts.append(f"[Source {i}: {source}]\n{content}\n")
        
        return "\n".join(context_parts)