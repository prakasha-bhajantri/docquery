
import os
from typing import TypedDict, List, Dict, Any, Optional
from dotenv import load_dotenv
load_dotenv()

try:
    from pypdf import PdfReader
    _HAS_PYPDF = True
except Exception:
    _HAS_PYPDF = False

try:
    import docx
    _HAS_DOCX = True
except Exception:
    _HAS_DOCX = False

try:
    from unstructured.partition.auto import partition
    _HAS_UNSTRUCTURED = True
except Exception:
    _HAS_UNSTRUCTURED = False

try:
    import tiktoken
    _HAS_TIKTOKEN = True
except Exception:
    _HAS_TIKTOKEN = False
    
# -------------------------
# 1) Parsing / Loaders
# -------------------------
def _extract_text_from_pdf(path: str) -> str:
    if _HAS_PYPDF:
        try:
            reader = PdfReader(path)
            pages = [p.extract_text() or "" for p in reader.pages]
            text = "\n".join(pages)
            if text.strip():
                return text
        except Exception:
            pass
    if _HAS_UNSTRUCTURED:
        try:
            elems = partition(filename=path)
            return "\n".join(getattr(e, "text", "") for e in elems)
        except Exception:
            pass
    return ""

def _extract_text_from_docx(path: str) -> str:
    if not _HAS_DOCX:
        return ""
    try:
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs if p.text)
    except Exception:
        return ""
    
    

def _extract_text_from_txt(path: str, encoding: str = "utf-8") -> str:
    try:
        with open(path, "r", encoding=encoding, errors="ignore") as f:
            return f.read()
    except Exception:
        return ""

def load_file(path: str) -> str:
    """
    Generic loader to extract text from pdf, docx, txt. Returns string (may be empty).
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"file not found: {path}")

    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _extract_text_from_pdf(path)
    if ext in (".docx", ".doc"):
        return _extract_text_from_docx(path)
    if ext == ".txt":
        return _extract_text_from_txt(path)

    # fallback to unstructured if available
    if _HAS_UNSTRUCTURED:
        try:
            elems = partition(filename=path)
            return "\n".join(getattr(e, "text", "") for e in elems)
        except Exception:
            pass

    # generic fallback
    return _extract_text_from_txt(path)

# -------------------------
# 2) Chunking
# -------------------------
def split_text_charwise(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    if not text:
        return []
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("invalid chunk_size/overlap")
    chunks = []
    start = 0
    L = len(text)
    while start < L:
        end = min(start + chunk_size, L)
        chunks.append(text[start:end])
        if end == L:
            break
        start = end - overlap
    return chunks

def split_text_tokenwise(text: str, chunk_size_tokens: int = 800, overlap_tokens: int = 100, model_name: str = "gpt2") -> List[str]:
    if not _HAS_TIKTOKEN:
        # approximate fallback: map tokens -> chars
        return split_text_charwise(text, chunk_size=chunk_size_tokens*4, overlap=overlap_tokens*4)
    enc = tiktoken.encoding_for_model(model_name) if model_name else tiktoken.get_encoding("gpt2")
    tokens = enc.encode(text)
    n = len(tokens)
    chunks = []
    start = 0
    while start < n:
        end = min(start + chunk_size_tokens, n)
        chunk_tokens = tokens[start:end]
        chunks.append(enc.decode(chunk_tokens))
        if end == n:
            break
        start = end - overlap_tokens
    return chunks
