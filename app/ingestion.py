"""
Document-ingestion utilities.
✓ Downloads a remote blob          (async httpx)
✓ Detects file-type & extracts text(pdfminer, python-docx, email.message)
✓ Falls back to OCR (pytesseract)  if PDF is image-only
✓ Splits text into semantic clauses with stable IDs
"""

import aiohttp, asyncio, mimetypes, pathlib, re, uuid, tempfile, subprocess
from typing import List
from pdfminer.high_level import extract_text as pdf_text
from docx import Document as DocxDocument
from email import message_from_string

CHUNK_SIZE = 2_000            # characters ≈ 300-350 tokens
OVERLAP    = 200

class Clause:
    def __init__(self, doc_id: str, idx: int, text: str):
        self.id   = f"{doc_id}_c{idx}"
        self.text = text

# ---------- download ------------------------------------------------------- #
async def _fetch(url: str, dest: pathlib.Path):
    async with aiohttp.ClientSession() as sess, sess.get(url) as resp:
        resp.raise_for_status()
        dest.write_bytes(await resp.read())
    return dest

async def download_blob(url: str) -> pathlib.Path:
    suffix = pathlib.Path(url.split("?")[0]).suffix or ".bin"
    tmp    = pathlib.Path(tempfile.mkstemp(suffix=suffix)[1])
    return await _fetch(url, tmp)

# ---------- type detect & extract ----------------------------------------- #
def _pdf_to_text(fp: pathlib.Path) -> str:
    txt = pdf_text(str(fp))
    if txt.strip():
        return txt
    # image-only → OCR each page via pdftoppm + tesseract
    ppm_dir = fp.parent/uuid.uuid4().hex; ppm_dir.mkdir()
    subprocess.run(["pdftoppm", "-png", str(fp), str(ppm_dir/"page")], check=True)
    out = []
    for img in sorted(ppm_dir.glob("page*.png")):
        out.append(subprocess.run(["tesseract", str(img), "-","-l","eng","--psm","6"],
                                  capture_output=True, text=True, check=True).stdout)
    return "\n".join(out)

def _docx_to_text(fp: pathlib.Path) -> str:
    doc = DocxDocument(fp)
    return "\n".join(p.text for p in doc.paragraphs)

def _email_to_text(fp: pathlib.Path) -> str:
    raw = fp.read_text(encoding="utf-8", errors="ignore")
    msg = message_from_string(raw)
    return msg.get_payload(decode=True).decode(errors="ignore") if msg.is_multipart() \
           else msg.get_payload()

EXTRACTORS = {
    ".pdf": _pdf_to_text,
    ".docx": _docx_to_text,
    ".eml": _email_to_text,
}

def extract_text(fp: pathlib.Path) -> str:
    ext = fp.suffix.lower()
    if ext not in EXTRACTORS:
        raise ValueError(f"Unsupported file-type {ext}")
    return EXTRACTORS[ext](fp)

# ---------- clause chunking ------------------------------------------------ #
_delim = re.compile(r"(\n{2,}|\. |\? |\! )")   # paragraph or sentence end

def chunk(text: str, doc_id: str) -> List[Clause]:
    tokens, current, clauses = 0, [], []
    for part in _delim.split(text):
        if not part.strip():
            continue
        current.append(part)
        tokens += len(part)
        if tokens >= CHUNK_SIZE:
            idx = len(clauses)
            joined = "".join(current).strip()
            clauses.append(Clause(doc_id, idx, joined))
            # start next chunk with overlap
            keep = joined[-OVERLAP:]
            current, tokens = [keep], len(keep)
    # remainder
    if current:
        clauses.append(Clause(doc_id, len(clauses), "".join(current).strip()))
    return clauses
