"""Execute recorded LLM requests against a local Ollama server (stdlib only).

The project's cloud workspace cannot reach the author's workstation, where Ollama + qwen2.5:7b run on a GPU.
The LangGraph workflow therefore writes each recommendation request (system prompt, user prompt, JSON schema,
options) to ``artifacts/llm_requests/requests.jsonl``; this script runs them on the workstation and appends
the *verbatim* model output with provenance to ``responses.jsonl``.  The workflow then resumes, validating each
response with Pydantic and the deterministic safety layer.  Nothing is generated or edited by hand.

    python scripts/ollama_batch.py --requests artifacts/llm_requests/requests.jsonl \
        --responses artifacts/llm_requests/responses.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
import urllib.request

BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def call(path: str, body: dict | None = None, timeout: int = 600) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", required=True)
    ap.add_argument("--responses", required=True)
    args = ap.parse_args()
    done = set()
    if os.path.exists(args.responses):
        for line in open(args.responses, encoding="utf-8"):
            if line.strip():
                done.add(json.loads(line)["request_hash"])
    tags = call("/api/tags")["models"]
    version = call("/api/version").get("version")
    reqs = [json.loads(line) for line in open(args.requests, encoding="utf-8") if line.strip()]
    todo = [r for r in reqs if r["request_hash"] not in done]
    print(f"{len(reqs)} requests, {len(todo)} to run")
    for r in todo:
        model = r["model"]
        tag = next((t for t in tags if t["name"] == model), None)
        body = {"model": model, "stream": False, "format": r["schema"], "options": r["options"],
                "messages": [{"role": "system", "content": r["system"]}, {"role": "user", "content": r["user"]}]}
        t0 = time.time()
        rec = {"request_hash": r["request_hash"], "model": model, "model_digest": tag["digest"] if tag else None,
               "ollama_version": version, "host": platform.node(), "started_at_unix": t0}
        try:
            js = call("/api/chat", body, timeout=900)
            rec.update(status="OK", content=js.get("message", {}).get("content", ""),
                       prompt_tokens=js.get("prompt_eval_count"), completion_tokens=js.get("eval_count"),
                       total_duration_ns=js.get("total_duration"), latency_s=time.time() - t0)
        except Exception as exc:
            rec.update(status="ERROR_TOOL", error=f"{type(exc).__name__}: {exc}"[:500], latency_s=time.time() - t0)
        with open(args.responses, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(r["request_hash"][:12], rec["status"], round(rec["latency_s"], 1), "s", flush=True)
    try:
        ps = call("/api/ps")
        with open(os.path.join(os.path.dirname(args.responses), "ollama_ps.json"), "w") as fh:
            json.dump({"api_ps": ps, "at": time.time()}, fh, indent=1)
    except Exception:
        pass


if __name__ == "__main__":
    main()
