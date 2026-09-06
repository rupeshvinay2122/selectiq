"""
FastAPI Candidate Discovery & Relevance Microservice
Exposes RESTful endpoints for candidate search, scoring, and honeypot auditing.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Query, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import ranker

app = FastAPI(
    title="SelectIQ Candidate Ranking Microservice",
    description="High-performance backend API for candidate retrieval, multi-factor scoring, and honeypot anomaly detection.",
    version="1.0.0"
)

# Mount static folder
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory candidate store loaded at startup
CANDIDATES_CACHE: List[Dict[str, Any]] = []
DATA_PATH_JSONL = Path("data/candidates.jsonl")
DATA_PATH_SAMPLE = Path("data/sample_candidates.json")

def load_data():
    """Loads candidate data into memory at server startup."""
    global CANDIDATES_CACHE
    if DATA_PATH_JSONL.exists():
        print(f"[INFO] Loading and auditing full dataset from {DATA_PATH_JSONL}...")
        start_t = time.time()
        valid = []
        total = 0
        honeypots = 0
        with open(DATA_PATH_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                total += 1
                cand = json.loads(line)
                is_fake, _ = ranker.check_is_honeypot(cand)
                if is_fake:
                    honeypots += 1
                else:
                    valid.append(cand)
        CANDIDATES_CACHE = valid
        elapsed = round(time.time() - start_t, 2)
        print(f"[INFO] Processed {total} total candidates in {elapsed}s.")
        print(f"[INFO] Filtered {honeypots} honeypots. Indexed {len(CANDIDATES_CACHE)} valid candidates in memory.")
    elif DATA_PATH_SAMPLE.exists():
        with open(DATA_PATH_SAMPLE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            CANDIDATES_CACHE = [c for c in raw if not ranker.check_is_honeypot(c)[0]]
        print(f"[INFO] Loaded {len(CANDIDATES_CACHE)} sample candidates into memory cache.")
    else:
        print("[WARN] No candidate dataset found.")

# Preload data on startup
load_data()

@app.get("/", response_class=FileResponse, tags=["General"])
def root():
    """Serves the SelectIQ Candidate Discovery UI."""
    return FileResponse("static/index.html")

@app.get("/api/v1/info", tags=["General"])
def api_info():
    """Returns JSON metadata about the candidate microservice."""
    return {
        "message": "Candidate Discovery & Ranking Microservice is online.",
        "docs_url": "/docs",
        "total_candidates_indexed": len(CANDIDATES_CACHE)
    }

@app.get("/api/v1/health", tags=["General"])
def health_check():
    return {
        "status": "healthy",
        "cached_candidates": len(CANDIDATES_CACHE),
        "timestamp": time.time()
    }

class SearchResponse(BaseModel):
    query: Dict[str, Any]
    latency_ms: float
    total_matches: int
    results: List[Dict[str, Any]]

@app.get("/api/v1/candidates/search", response_model=SearchResponse, tags=["Search & Ranking"])
def search_candidates(
    skills: str = Query("python, fastapi, sql", description="Comma-separated list of required skills"),
    min_yoe: float = Query(4.0, ge=0.0, description="Minimum years of experience"),
    max_yoe: float = Query(10.0, ge=0.0, description="Maximum years of experience"),
    limit: int = Query(10, ge=1, le=500, description="Number of top candidates to return")
):
    """
    Real-time candidate discovery endpoint using Min-Heap ranking.
    """
    start_time = time.time()
    target_skills = [s.strip() for s in skills.split(",") if s.strip()]

    ranked_results = ranker.search_top_candidates(
        candidates=CANDIDATES_CACHE,
        target_skills=target_skills,
        min_yoe=min_yoe,
        max_yoe=max_yoe,
        limit=limit
    )

    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    return SearchResponse(
        query={
            "skills": target_skills,
            "min_yoe": min_yoe,
            "max_yoe": max_yoe,
            "limit": limit
        },
        latency_ms=elapsed_ms,
        total_matches=len(ranked_results),
        results=ranked_results
    )

class AuditRequest(BaseModel):
    candidate: Dict[str, Any] = Field(..., description="Candidate JSON payload to audit")

class AuditResponse(BaseModel):
    is_honeypot: bool
    reasons: List[str]
    verdict: str

@app.post("/api/v1/candidates/audit", response_model=AuditResponse, tags=["Safety Audit"])
def audit_candidate(payload: AuditRequest):
    """
    Audits a candidate profile against deterministic honeypot rules.
    Detects salary inversion, graduation timeline conflicts, and skill bluffing.
    """
    is_fake, reasons = ranker.check_is_honeypot(payload.candidate)
    return AuditResponse(
        is_honeypot=is_fake,
        reasons=reasons,
        verdict="REJECTED: Honeypot / Scrambled Profile" if is_fake else "PASSED: Valid Candidate"
    )
