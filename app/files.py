"""Extract plain text from uploaded files so it can be dropped into chat context."""
import io

from docx import Document
from pypdf import PdfReader

MAX_CHARS = 20_000


def extract_text(filename: str, content: bytes) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif ext == "docx":
        doc = Document(io.BytesIO(content))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        text = content.decode("utf-8", errors="replace")

    text = text.strip()
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + f"\n\n[... truncated, file exceeded {MAX_CHARS} characters ...]"
    return text
