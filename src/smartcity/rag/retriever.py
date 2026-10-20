"""FAISS-backed retrieval over the approved knowledge corpus.

Security: retrieved passages are untrusted DATA.  They are returned as quoted evidence only, never executed,
and the index is loaded only after its corpus hash matches the manifest (no pickle deserialisation: FAISS
native format + JSON).
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np

from smartcity import settings
from smartcity.contracts import Authority, RetrievedEvidence
from smartcity.knowledge.corpus import build_chunks
from smartcity.utils import sha256_json, write_json

IDX_DIR = settings.ROOT / "knowledge" / "indexes"
MODEL_DIR = settings.ROOT / "data" / "models" / "sentence-transformers__all-MiniLM-L6-v2"

_MODEL = None


def embedder():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        src = str(MODEL_DIR) if MODEL_DIR.exists() else settings.load("rag")["rag"]["embedding_model"]
        _MODEL = SentenceTransformer(src, device="cpu")
    return _MODEL


def build_index() -> dict:
    import faiss

    cfg = settings.load("rag")["rag"]
    model = embedder()
    tok = model.tokenizer
    chunks = build_chunks(tokenizer=tok)
    if not chunks:
        raise SystemExit("NOT_RUN: no approved documents")
    lengths = [len(tok.tokenize(c["text"])) for c in chunks]
    over = sum(1 for n in lengths if n > model.max_seq_length - 2)
    t0 = time.time()
    emb = model.encode([c["text"] for c in chunks], batch_size=32, normalize_embeddings=True, show_progress_bar=False)
    index = faiss.IndexFlatIP(emb.shape[1])
    index.add(np.asarray(emb, dtype=np.float32))
    IDX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(IDX_DIR / "knowledge.faiss"))
    (IDX_DIR / "chunks.json").write_text(json.dumps(chunks, indent=1))
    manifest = {"embedding_model": cfg["embedding_model"], "local_model_dir": str(MODEL_DIR.relative_to(settings.ROOT)),
                "n_chunks": len(chunks), "dim": int(emb.shape[1]), "corpus_hash": sha256_json(chunks)[:16],
                "chunk_token_max": int(max(lengths)), "chunks_over_model_limit": over,
                "model_max_seq_length": model.max_seq_length, "build_seconds": round(time.time() - t0, 2),
                "documents": sorted({c["document_id"] for c in chunks})}
    write_json(IDX_DIR / "index_manifest.json", manifest)
    return manifest


class Retriever:
    def __init__(self):
        import faiss

        self.manifest = json.loads((IDX_DIR / "index_manifest.json").read_text())
        self.chunks = json.loads((IDX_DIR / "chunks.json").read_text())
        if sha256_json(self.chunks)[:16] != self.manifest["corpus_hash"]:
            raise ValueError("chunk store does not match index manifest hash; refusing to load")
        self.index = faiss.read_index(str(IDX_DIR / "knowledge.faiss"))
        self.cfg = settings.load("rag")["rag"]
        self.by_id = {c["chunk_id"]: c for c in self.chunks}

    def search(self, query: str, k: int | None = None, authorities: list[str] | None = None) -> list[RetrievedEvidence]:
        k = k or self.cfg["retrieve_k"]
        q = embedder().encode([query], normalize_embeddings=True)
        scores, idx = self.index.search(np.asarray(q, dtype=np.float32), min(len(self.chunks), k * 3))
        out = []
        for s, i in zip(scores[0], idx[0]):
            if i < 0:
                continue
            c = self.chunks[i]
            if authorities and c["authority"] not in authorities:
                continue
            out.append(RetrievedEvidence(chunk_id=c["chunk_id"], document_id=c["document_id"], title=c["title"],
                                         authority=Authority(c["authority"]), score=float(s), text=c["text"],
                                         source_url=c.get("source_url")))
            if len(out) >= k:
                break
        return out

    def evidence(self, query: str) -> tuple[str, list[RetrievedEvidence]]:
        """Return ('SUPPORTED'|'INSUFFICIENT_EVIDENCE', top final_context_k passages above min_score)."""
        hits = [h for h in self.search(query) if h.score >= self.cfg["min_score"]]
        hits = hits[: self.cfg["final_context_k"]]
        return ("SUPPORTED" if hits else "INSUFFICIENT_EVIDENCE"), hits


def evaluate(query_file: Path | None = None) -> dict:
    """Recall@k and MRR against a labelled query set (labels drafted by the project; review status recorded)."""
    query_file = query_file or settings.ROOT / "knowledge" / "retrieval_eval_queries.csv"
    r = Retriever()
    rows = list(csv.DictReader(open(query_file, encoding="utf-8")))
    k = r.cfg["retrieve_k"]
    indexed = set(r.manifest["documents"])
    per, recalls, rr, status_ok, skipped = [], [], [], [], []
    for q in rows:
        rel_docs = {d.strip() for d in q["relevant_document_ids"].split(";") if d.strip()}
        if rel_docs - indexed:  # labelled document was not downloaded/approved: report, do not score
            skipped.append({"query_id": q["query_id"], "missing_documents": sorted(rel_docs - indexed)})
            per.append({"query_id": q["query_id"], "query": q["query"], "expected_status": q["expected_status"].strip(),
                        "status": "RELEVANT_DOC_NOT_INDEXED", "status_correct": None, f"recall@{k}": None,
                        "reciprocal_rank": None, "top1": None, "top1_score": None, "latency_s": None,
                        "review_status": q.get("review_status", "")})
            continue
        t0 = time.time()
        hits = r.search(q["query"], k=k)
        status, ev = r.evidence(q["query"])
        latency = time.time() - t0
        ranks = [i + 1 for i, h in enumerate(hits) if h.document_id in rel_docs]
        recall = (len({h.document_id for h in hits} & rel_docs) / len(rel_docs)) if rel_docs else None
        mrr = (1 / ranks[0]) if ranks else 0.0
        exp_status = q["expected_status"].strip()
        ok = status == exp_status
        status_ok.append(ok)
        if rel_docs:
            recalls.append(recall)
            rr.append(mrr)
        per.append({"query_id": q["query_id"], "query": q["query"], "expected_status": exp_status, "status": status,
                    "status_correct": ok, f"recall@{k}": recall, "reciprocal_rank": mrr if rel_docs else None,
                    "top1": hits[0].chunk_id if hits else None, "top1_score": hits[0].score if hits else None,
                    "latency_s": round(latency, 4), "review_status": q.get("review_status", "")})
    summary = {"n_queries": len(rows), "n_scored": len(status_ok), "n_skipped_missing_docs": len(skipped),
               "skipped": skipped, "k": k, f"mean_recall@{k}": float(np.mean(recalls)) if recalls else None,
               "mrr": float(np.mean(rr)) if rr else None,
               "status_accuracy": float(np.mean(status_ok)) if status_ok else None,
               "corpus_hash": r.manifest["corpus_hash"], "min_score": r.cfg["min_score"],
               "label_review_status": sorted({q.get("review_status", "") for q in rows})}
    out = settings.ROOT / "artifacts" / "retrieval"
    write_json(out / "retrieval_eval.json", {"summary": summary, "per_query": per})
    exp = settings.ROOT / "reports" / "experiments" / "retrieval_metrics.csv"
    with open(exp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(per[0].keys()))
        w.writeheader()
        w.writerows(per)
    return summary
