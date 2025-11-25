"""
FastAPI Backend for Autonomous QA Agent
Main application entry point
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import shutil
from pathlib import Path
import logging

from services.document_parser import DocumentParser
from services.vector_store import VectorStore
from services.embeddings import EmbeddingService
from services.rag_service import RAGService
from services.test_case_generator import TestCaseGenerator
from services.script_generator import ScriptGenerator
from config import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Autonomous QA Agent API",
    description="API for test case and Selenium script generation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize settings
settings = Settings()

# Global service instances
document_parser = DocumentParser()
embedding_service = EmbeddingService()
vector_store = VectorStore(embedding_service)
rag_service = RAGService(vector_store, embedding_service)
test_case_generator = TestCaseGenerator(rag_service)
script_generator = ScriptGenerator(rag_service)

# Data directories
UPLOAD_DIR = Path("data/uploads")
SUPPORT_DOCS_DIR = Path("data/support_documents")
HTML_DIR = Path("data/html")
SCRIPTS_DIR = Path("generated_scripts")

# Create directories
for dir_path in [UPLOAD_DIR, SUPPORT_DOCS_DIR, HTML_DIR, SCRIPTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


# ============= Models =============

class KnowledgeBaseStatus(BaseModel):
    status: str
    total_documents: int
    total_chunks: int
    embedding_model: str
    message: str


class TestCaseRequest(BaseModel):
    query: str
    num_cases: Optional[int] = 10


class TestCase(BaseModel):
    test_id: str
    feature: str
    test_scenario: str
    test_type: str
    preconditions: Optional[str]
    test_steps: List[str]
    expected_result: str
    grounded_in: List[str]
    priority: str


class ScriptGenerationRequest(BaseModel):
    test_case: TestCase
    html_content: str
    browser: Optional[str] = "chrome"


class HealthCheck(BaseModel):
    status: str
    vector_db_status: str
    documents_count: int


# ============= Endpoints =============

@app.get("/", response_model=dict)
async def root():
    """Root endpoint"""
    return {
        "message": "Autonomous QA Agent API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    try:
        db_status = "connected" if vector_store.is_initialized() else "not_initialized"
        doc_count = vector_store.get_document_count()
        
        return HealthCheck(
            status="healthy",
            vector_db_status=db_status,
            documents_count=doc_count
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Service unhealthy")


@app.post("/upload/support-documents")
async def upload_support_documents(files: List[UploadFile] = File(...)):
    """Upload support documents (MD, TXT, JSON, PDF)"""
    try:
        uploaded_files = []
        
        for file in files:
            # Validate file type
            allowed_extensions = ['.md', '.txt', '.json', '.pdf', '.docx']
            file_ext = os.path.splitext(file.filename)[1].lower()
            
            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type {file_ext} not supported. Allowed: {allowed_extensions}"
                )
            
            # Save file
            file_path = SUPPORT_DOCS_DIR / file.filename
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            uploaded_files.append({
                "filename": file.filename,
                "path": str(file_path),
                "size": os.path.getsize(file_path)
            })
        
        logger.info(f"Uploaded {len(uploaded_files)} support documents")
        
        return {
            "message": f"Successfully uploaded {len(uploaded_files)} documents",
            "files": uploaded_files
        }
    
    except Exception as e:
        logger.error(f"Error uploading documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/html")
async def upload_html(file: UploadFile = File(...)):
    """Upload target HTML file"""
    try:
        # Validate HTML file
        if not file.filename.endswith('.html'):
            raise HTTPException(
                status_code=400,
                detail="Only HTML files are allowed"
            )
        
        # Save HTML file
        file_path = HTML_DIR / file.filename
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Parse HTML to extract structure
        html_content = file_path.read_text(encoding='utf-8')
        html_info = document_parser.parse_html(html_content)
        
        logger.info(f"Uploaded HTML file: {file.filename}")
        
        return {
            "message": "HTML file uploaded successfully",
            "filename": file.filename,
            "path": str(file_path),
            "elements_count": len(html_info.get('elements', [])),
            "forms_count": len(html_info.get('forms', []))
        }
    
    except Exception as e:
        logger.error(f"Error uploading HTML: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/knowledge-base/build", response_model=KnowledgeBaseStatus)
async def build_knowledge_base(background_tasks: BackgroundTasks):
    """Build vector database from uploaded documents"""
    try:
        logger.info("Starting knowledge base build...")
        
        # Get all support documents
        support_files = list(SUPPORT_DOCS_DIR.glob("*"))
        html_files = list(HTML_DIR.glob("*.html"))
        
        if not support_files and not html_files:
            raise HTTPException(
                status_code=400,
                detail="No documents uploaded. Please upload documents first."
            )
        
        all_documents = []
        
        # Parse support documents
        for file_path in support_files:
            try:
                parsed_doc = document_parser.parse_file(file_path)
                all_documents.append(parsed_doc)
                logger.info(f"Parsed: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to parse {file_path.name}: {str(e)}")
        
        # Parse HTML files
        for file_path in html_files:
            try:
                html_content = file_path.read_text(encoding='utf-8')
                parsed_doc = document_parser.parse_html_file(html_content, str(file_path))
                all_documents.append(parsed_doc)
                logger.info(f"Parsed HTML: {file_path.name}")
            except Exception as e:
                logger.warning(f"Failed to parse HTML {file_path.name}: {str(e)}")
        
        # Build vector store
        total_chunks = vector_store.build_from_documents(all_documents)
        
        logger.info(f"Knowledge base built: {len(all_documents)} documents, {total_chunks} chunks")
        
        return KnowledgeBaseStatus(
            status="success",
            total_documents=len(all_documents),
            total_chunks=total_chunks,
            embedding_model=settings.EMBEDDING_MODEL,
            message="Knowledge base built successfully"
        )
    
    except Exception as e:
        logger.error(f"Error building knowledge base: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/test-cases/generate")
async def generate_test_cases(request: TestCaseRequest):
    """Generate test cases based on query"""
    try:
        logger.info(f"Generating test cases for query: {request.query}")
        
        # Check if knowledge base is built
        if not vector_store.is_initialized():
            raise HTTPException(
                status_code=400,
                detail="Knowledge base not initialized. Please build it first."
            )
        
        # Generate test cases
        test_cases = test_case_generator.generate_test_cases(
            query=request.query,
            num_cases=request.num_cases
        )
        
        logger.info(f"Generated {len(test_cases)} test cases")
        
        return {
            "query": request.query,
            "total_cases": len(test_cases),
            "test_cases": test_cases
        }
    
    except Exception as e:
        logger.error(f"Error generating test cases: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/selenium-script/generate")
async def generate_selenium_script(request: ScriptGenerationRequest):
    """Generate Selenium script from test case"""
    try:
        logger.info(f"Generating Selenium script for test: {request.test_case.test_id}")
        
        # Generate script
        script_result = script_generator.generate_script(
            test_case=request.test_case.dict(),
            html_content=request.html_content,
            browser=request.browser
        )
        
        # Save script to file
        script_filename = f"{request.test_case.test_id}_script.py"
        script_path = SCRIPTS_DIR / script_filename
        
        with open(script_path, "w") as f:
            f.write(script_result['script'])
        
        logger.info(f"Generated script saved to: {script_path}")
        
        return {
            "test_id": request.test_case.test_id,
            "script": script_result['script'],
            "script_path": str(script_path),
            "selectors_used": script_result.get('selectors', []),
            "explanation": script_result.get('explanation', '')
        }
    
    except Exception as e:
        logger.error(f"Error generating script: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/list")
async def list_documents():
    """List all uploaded documents"""
    try:
        support_docs = [
            {
                "filename": f.name,
                "type": "support",
                "size": os.path.getsize(f),
                "path": str(f)
            }
            for f in SUPPORT_DOCS_DIR.glob("*")
        ]
        
        html_docs = [
            {
                "filename": f.name,
                "type": "html",
                "size": os.path.getsize(f),
                "path": str(f)
            }
            for f in HTML_DIR.glob("*.html")
        ]
        
        return {
            "support_documents": support_docs,
            "html_files": html_docs,
            "total": len(support_docs) + len(html_docs)
        }
    
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/documents/clear")
async def clear_documents():
    """Clear all uploaded documents and reset knowledge base"""
    try:
        # Clear directories
        for dir_path in [SUPPORT_DOCS_DIR, HTML_DIR]:
            for file in dir_path.glob("*"):
                file.unlink()
        
        # Reset vector store
        vector_store.reset()
        
        logger.info("All documents cleared and knowledge base reset")
        
        return {"message": "All documents cleared successfully"}
    
    except Exception as e:
        logger.error(f"Error clearing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scripts/list")
async def list_generated_scripts():
    """List all generated Selenium scripts"""
    try:
        scripts = [
            {
                "filename": f.name,
                "size": os.path.getsize(f),
                "created": os.path.getctime(f),
                "path": str(f)
            }
            for f in SCRIPTS_DIR.glob("*.py")
        ]
        
        return {
            "scripts": scripts,
            "total": len(scripts)
        }
    
    except Exception as e:
        logger.error(f"Error listing scripts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )