from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from core.rag_service import rag_service, TEMP_UPLOAD_DIR # Import service instance and path
from typing import List
import os

# --- Pydantic Models ---
class QueryRequest(BaseModel):
    query: str

class SelectRequest(BaseModel):
    filename: str

class DocumentListResponse(BaseModel):
    documents: List[str]
    selected_document: str

# --- FastAPI App ---
app = FastAPI(title="DocQuery RAG API")

@app.get("/documents", response_model=DocumentListResponse)
def list_documents():
    """Endpoint to list all documents and the currently selected one."""
    return {
        "documents": rag_service.get_document_list(),
        "selected_document": rag_service.selected_document
    }

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Endpoint to upload a file, index it, and update the RAG service."""
    if not file.filename or not file.filename.lower().endswith(('.pdf', '.txt', '.docx')):
        raise HTTPException(status_code=400, detail="Unsupported file type or missing filename.")

    # Save the uploaded file temporarily
    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
    file_location = os.path.join(TEMP_UPLOAD_DIR, file.filename)
    
    try:
        # Write the file chunk by chunk
        with open(file_location, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024) # 1MB chunk size
                if not chunk:
                    break
                buffer.write(chunk)
        
        # Asynchronously process and index the file
        result = await rag_service.upload_and_index_document(file_location)
        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        # Clean up the temporary file if indexing fails
        if os.path.exists(file_location):
            os.remove(file_location)
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")

@app.post("/select_document")
def select_document(request: SelectRequest):
    """Endpoint to select the document to use for QA."""
    if rag_service.set_selected_document(request.filename):
        return {"status": "success", "message": f"Document {request.filename} selected."}
    raise HTTPException(status_code=404, detail=f"Document {request.filename} not found.")

@app.delete("/document/{filename}")
async def delete_document(filename: str):
    """Endpoint to delete a document from the index."""
    success, message = await rag_service.delete_document(filename)
    if success:
        return {"status": "success", "message": message}
    raise HTTPException(status_code=500, detail=message)

@app.post("/query")
async def chat_query(request: QueryRequest):
    """Endpoint to submit a query and get a chat response."""
    try:
        response_text = await rag_service.chat_query(request.query)
        return {"response": response_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")