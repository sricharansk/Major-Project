"""Approved knowledge registry and chunking.

Only files listed in ``knowledge/source_registry.csv`` with ``approved=yes`` are indexed; each file's SHA-256
must match the registry (allowlist + tamper check).  Every chunk keeps its document's authority label.
"""

from __future__ import annotations

import csv
import hashlib
import html
import re
from pathlib import Path

from smartcity import settings

REGISTRY = settings.ROOT / "knowledge" / "source_registry.csv"
FIELDS = ["document_id", "title", "publisher", "source_url", "jurisdiction", "document_type", "published_date",
          "retrieved_at", "license", "sha256", "version", "authority_level", "local_path", "approved"]


def read_registry() -> list[dict]:
    if not REGISTRY.exists():
        return []
    with open(REGISTRY, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_registry(rows: list[dict]):
    with open(REGISTRY, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def extract_text(p: Path) -> str:
    raw = p.read_bytes()
    if p.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(p))
            return "\n".join((pg.extract_text() or "") for pg in reader.pages)
        except Exception as exc:
            raise RuntimeError(f"PDF extraction failed for {p.name}: {exc}") from exc
    text = raw.decode("utf-8", errors="replace")
    if p.suffix.lower() in (".htm", ".html"):
        text = re.sub(r"(?is)<(script|style|nav|header|footer).*?</\1>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def chunk_words(text: str, target_tokens: int, overlap_tokens: int, tokenizer=None) -> list[str]:
    """Chunk on paragraph boundaries to ~target word-pieces; never silently truncate (callers verify length)."""
    def ntok(s: str) -> int:
        return len(tokenizer.tokenize(s)) if tokenizer is not None else int(len(s.split()) * 1.3)

    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    pieces: list[str] = []
    for p in paras:  # split over-long paragraphs by sentences / words
        if ntok(p) <= target_tokens:
            pieces.append(p)
            continue
        words = p.split()
        step = max(1, int(target_tokens / 1.4))
        for i in range(0, len(words), step):
            pieces.append(" ".join(words[i:i + step]))
    chunks, cur = [], []
    for piece in pieces:
        if cur and ntok(" ".join(cur + [piece])) > target_tokens:
            chunks.append(" ".join(cur))
            # overlap: carry trailing words
            tail = " ".join(cur).split()[-int(overlap_tokens / 1.3):]
            cur = [" ".join(tail)] if tail else []
        cur.append(piece)
    if cur:
        chunks.append(" ".join(cur))
    return [c for c in chunks if len(c.split()) >= 12]


def build_chunks(tokenizer=None) -> list[dict]:
    cfg = settings.load("rag")["rag"]
    chunks = []
    for doc in read_registry():
        if doc.get("approved") != "yes":
            continue
        p = settings.ROOT / doc["local_path"]
        if not p.exists():
            raise FileNotFoundError(f"registered document missing: {p}")
        sha = file_sha(p)
        if sha != doc["sha256"]:
            raise ValueError(f"hash mismatch for {doc['document_id']} (allowlist violation)")
        text = extract_text(p)
        for i, c in enumerate(chunk_words(text, cfg["chunk_tokens_target"], cfg["chunk_overlap_tokens"], tokenizer)):
            chunks.append({"chunk_id": f"{doc['document_id']}#c{i:04d}", "document_id": doc["document_id"],
                           "title": doc["title"], "authority": doc["authority_level"], "source_url": doc["source_url"],
                           "text": c})
    return chunks
