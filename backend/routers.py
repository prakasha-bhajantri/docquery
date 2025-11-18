import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from .core.vector_store import index_file_and_return_index
from .core.rag_graph import answer_query_with_graph

router = APIRouter()

# ensure upload dir
UPLOAD_DIR = os.path.join(os.getcwd(), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --------------------------
# Request Model for Query
# --------------------------
class QueryRequest(BaseModel):
    question: str
    index_name: str
    top_k: int = 4


# --------------------------
# UPLOAD ENDPOINT
# --------------------------
@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    """
    Upload a file and create a new vector index.
    Returns: { "index_name": "auto_generated_index" }
    """
    path = os.path.join(UPLOAD_DIR, file.filename)

    # save file
    with open(path, "wb") as f:
        f.write(await file.read())

    # index file (auto index name)
    res = index_file_and_return_index(path)

    if "error" in res:
        raise HTTPException(status_code=500, detail=res["error"])

    return res

# --------------------------
# QUERY ENDPOINT
# --------------------------
@router.post("/query")
async def query(payload: QueryRequest):
    """
    Ask a question on a previously indexed file.
    """
    res = answer_query_with_graph(
        payload.question,
        payload.index_name,
        payload.top_k
    )

    if res.get("error"):
        raise HTTPException(status_code=500, detail=res["error"])

    return {
        "answer": res["answer"],
        "retrieved": res["retrieved"]
    }