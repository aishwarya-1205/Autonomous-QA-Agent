from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # LLM Configuration
    LLM_PROVIDER: str = "groq"  # groq, ollama, openai
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Model Configuration
    LLM_MODEL: str = "mixtral-8x7b-32768"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    LLM_TEMPERATURE: float = 0.1
    MAX_TOKENS: int = 4096
    
    # Vector DB Configuration
    VECTOR_DB_TYPE: str = "chromadb"  # chromadb or faiss
    VECTOR_DB_PATH: str = "./data/vector_db"
    COLLECTION_NAME: str = "qa_documents"
    
    # Chunking Configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    
    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()