import os
import math
import uuid
from typing import TypedDict, List, Dict, Any, Optional
from .data_processor import *

# embeddings
from sentence_transformers import SentenceTransformer

# chroma (new client API)
from chromadb import PersistentClient

from dotenv import load_dotenv
load_dotenv()

try:
    import tiktoken
    _HAS_TIKTOKEN = True
except Exception:
    _HAS_TIKTOKEN = False


# sentence-transformers model (small & fast)
_EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_EMBED_BATCH = int(os.getenv("EMBED_BATCH", "32"))
_embed_model = SentenceTransformer(_EMBED_MODEL)

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./data/chroma_db")
DEFAULT_INDEX = os.getenv("DEFAULT_INDEX", "docquery_default")
os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)

# chroma client (PersistentClient for local storage)
_chroma_client = PersistentClient(path=CHROMA_PERSIST_DIR)

# -------------------------
# 3) Embeddings
# -------------------------
def create_embeddings(texts: List[str], batch_size: int = _EMBED_BATCH) -> List[List[float]]:
    """
    Use sentence-transformers model to produce embeddings (python lists).
    """
    if not texts:
        return []
    embeddings = []
    total = len(texts)
    for i in range(0, total, batch_size):
        batch = texts[i:i+batch_size]
        vecs = _embed_model.encode(batch, convert_to_numpy=True)
        for v in vecs:
            embeddings.append([float(x) for x in v])
    return embeddings


# -------------------------
# 4) Vector DB (Chroma) helpers
# -------------------------
# Helper to get/create collection
def _get_or_create_collection(name: str):
    try:
        return _chroma_client.get_collection(name)
    except Exception:
        # create_collection signature may vary; this is the common one
        return _chroma_client.create_collection(name)
    
def store_chunks(index_name: str, ids: List[str], chunks: List[str], embeddings: List[List[float]], metadatas: Optional[List[dict]] = None) -> Dict[str, Any]:
    coll = _get_or_create_collection(index_name)
    metadatas = metadatas or [{} for _ in chunks]
    coll.add(ids=ids, documents=chunks, metadatas=metadatas, embeddings=embeddings)
    return {"collection": index_name, "n_added": len(chunks)}

def query_index(index_name: str, query_embedding: List[float], top_k: int = 4, include: Optional[List[str]] = None) -> Dict[str, Any]:
    coll = _get_or_create_collection(index_name)
    include = include or ["documents", "metadatas", "distances"]
    res = coll.query(query_embeddings=[query_embedding], n_results=top_k, include=include)
    return res


# 5) High-level indexer (ingest one file)
# -------------------------
def index_file(
    path: str,
    index_name: Optional[str] = None,
    use_token_split: bool = False,
    chunk_size: int = 1000,
    overlap: int = 200,
    metadata: Optional[dict] = None
) -> Dict[str, Any]:
    """
    End-to-end indexing for a single file.
    Returns metadata: {status, index_name, n_chunks, storage}
    """
    if index_name is None:
        index_name = f"session_{uuid.uuid4().hex}"

    # 1) load
    text = load_file(path)
    if not text or not text.strip():
        return {"status": "empty", "indexed": 0, "reason": "no text extracted", "index_name": index_name}

    # 2) split
    if use_token_split and _HAS_TIKTOKEN:
        chunks = split_text_tokenwise(text, chunk_size_tokens=math.floor(chunk_size/4), overlap_tokens=math.floor(overlap/4))
    else:
        chunks = split_text_charwise(text, chunk_size=chunk_size, overlap=overlap)

    # 3) prepare ids & metadatas
    base_id = uuid.uuid4().hex
    ids = [f"{base_id}_{i}" for i in range(len(chunks))]
    metadatas = []
    fname = os.path.basename(path)
    for i in range(len(chunks)):
        md = {"source": fname, "chunk_index": i}
        if metadata:
            md.update(metadata)
        metadatas.append(md)

    # 4) embed
    embeddings = create_embeddings(chunks)

    # 5) store
    storage_info = store_chunks(index_name, ids=ids, chunks=chunks, embeddings=embeddings, metadatas=metadatas)

    return {"status": "ok", "index_name": index_name, "n_chunks": len(chunks), "storage": storage_info}

# -------------------------
# 6) Query helpers for RAG
# -------------------------
def embed_query(query: str) -> List[float]:
    emb = create_embeddings([query])
    return emb[0] if emb else []

def retrieve_topk(index_name: str, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """
    Embeds query and retrieves top_k hits from chroma.
    Returns list of {"text","metadata","score"}
    """
    q_emb = embed_query(query)
    raw = query_index(index_name, q_emb, top_k=top_k, include=["documents","metadatas","distances"])
    hits = []
    docs_outer = raw.get("documents", [])
    metas_outer = raw.get("metadatas", [])
    dists_outer = raw.get("distances", [])
    if docs_outer and len(docs_outer) > 0:
        docs = docs_outer[0]
        metas = metas_outer[0] if metas_outer and len(metas_outer) > 0 else [{}]*len(docs)
        dists = dists_outer[0] if dists_outer and len(dists_outer) > 0 else [0.0]*len(docs)
        for t, m, d in zip(docs, metas, dists):
            hits.append({"text": t, "metadata": m, "score": float(d)})
    return hits

# 9) Example usage helpers (for routers)
# -------------------------
def index_file_and_return_index(path: str, **kwargs) -> Dict[str, Any]:
    """
    Thin wrapper to call index_file and return helpful JSON for routers.
    """
    return index_file(path, **kwargs)