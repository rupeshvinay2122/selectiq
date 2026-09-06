"""
Candidate Discovery & Relevance Engine
Implements deterministic honeypot detection, multi-signal scoring, and Min-Heap streaming ranking.
"""

from __future__ import annotations
import heapq
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CURRENT_YEAR = 2026

SERVICE_COMPANIES = {
    "tcs", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "l&t", "deloitte"
}

def check_is_honeypot(cand: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Deterministic safety audit checking for fraudulent and corrupted profile anomalies.
    Returns: (is_fake, reasons)
    """
    reasons = []
    profile = cand.get("profile") or {}
    skills = cand.get("skills") or []
    signals = cand.get("redrob_signals") or {}
    education = cand.get("education") or []

    # 1. Salary Inversion check
    sal_range = signals.get("expected_salary_range_inr_lpa") or {}
    sal_min = sal_range.get("min", 0) or 0
    sal_max = sal_range.get("max", 0) or 0
    if sal_min > 0 and sal_max > 0 and sal_min > sal_max:
        reasons.append(f"Salary inversion anomaly: min ({sal_min}) > max ({sal_max})")

    # 2. Timeline Conflict (YOE vs Graduation Year)
    yoe = profile.get("years_of_experience", 0) or 0
    grad_years = [e.get("end_year") for e in education if e.get("end_year")]
    if grad_years and yoe > 0:
        min_grad = min(grad_years)
        max_possible_yoe = CURRENT_YEAR - min_grad + 2
        if yoe > max_possible_yoe + 6 and yoe > 2:
            reasons.append(f"Timeline contradiction: claimed {yoe} YOE but graduated in {min_grad}")

    # 3. Expert Skill Duration Bluffing
    expert_zero = [
        s.get("name") for s in skills
        if s.get("proficiency") in ["expert", "advanced"] and (s.get("duration_months", 0) or 0) == 0
    ]
    if len(expert_zero) >= 3:
        reasons.append(f"Skill bluffing: claims advanced/expert proficiency with 0 duration in: {', '.join(expert_zero[:3])}")

    return (len(reasons) > 0, reasons)


def score_candidate(
    cand: Dict[str, Any],
    target_skills: Optional[List[str]] = None,
    min_yoe: float = 4.0,
    max_yoe: float = 10.0
) -> Tuple[float, Dict[str, Any]]:
    """
    Calculates composite relevance score for a candidate between 0.0 and 1.0.
    """
    profile = cand.get("profile") or {}
    history = cand.get("career_history") or []
    skills = cand.get("skills") or []
    signals = cand.get("redrob_signals") or {}

    # Default target skills if not supplied
    if not target_skills:
        target_skills = ["python", "fastapi", "docker", "sql", "redis"]
    target_skills_set = {s.lower().strip() for s in target_skills if s.strip()}

    # 1. Skills Coverage (Max 40 pts)
    matched_skills = []
    cand_skill_names = {s.get("name", "").lower(): s for s in skills if s.get("name")}
    for ts in target_skills_set:
        if ts in cand_skill_names:
            matched_skills.append(cand_skill_names[ts].get("name"))

    skills_score = (len(matched_skills) / max(len(target_skills_set), 1)) * 40.0

    # 2. Experience Fit (Max 30 pts)
    yoe = float(profile.get("years_of_experience", 0) or 0)
    min_yoe = max(0.0, float(min_yoe))
    max_yoe = max(min_yoe, float(max_yoe))

    if min_yoe <= yoe <= max_yoe:
        yoe_score = 30.0
    elif yoe < min_yoe:
        yoe_score = max(5.0, 30.0 * (yoe / min_yoe)) if min_yoe > 0 else 30.0
    else:
        yoe_score = max(10.0, 30.0 * (max_yoe / yoe)) if yoe > 0 else 10.0

    # 3. Company Pedigree (Max 15 pts)
    companies = [h.get("company", "").lower() for h in history if h.get("company")]
    is_consulting_only = len(companies) > 0 and all(
        any(sc in comp for sc in SERVICE_COMPANIES) for comp in companies if comp
    )
    comp_score = 3.0 if is_consulting_only else 15.0

    # 4. Behavioral & Availability Signals (Max 15 pts)
    open_to_work = signals.get("open_to_work_flag", True)
    resp_rate = float(signals.get("recruiter_response_rate", 0.5) or 0.5)
    notice = int(signals.get("notice_period_days", 30) or 30)

    avail_score = 0.0
    if open_to_work:
        avail_score += 5.0
    avail_score += min(5.0, resp_rate * 5.0)
    if notice <= 30:
        avail_score += 5.0
    elif notice <= 60:
        avail_score += 3.0
    else:
        avail_score += 1.0

    total_score = (skills_score + yoe_score + comp_score + avail_score) / 100.0

    features = {
        "matched_skills": matched_skills,
        "yoe": yoe,
        "open_to_work": open_to_work,
        "notice_period_days": notice,
        "response_rate": resp_rate,
        "is_consulting_only": is_consulting_only
    }
    return round(total_score, 4), features


def generate_reasoning(cand: Dict[str, Any], score: float, features: Dict[str, Any]) -> str:
    """
    Generates an explainable recruiter-friendly summary.
    """
    profile = cand.get("profile") or {}
    name = profile.get("anonymized_name", "Candidate")
    title = profile.get("current_title", "Software Engineer")
    yoe = features.get("yoe", 0)
    matched = features.get("matched_skills", [])
    skills_text = ", ".join(matched[:3]) if matched else "core engineering"

    avail = "Actively available" if features.get("open_to_work") else "Passively open"
    notice = features.get("notice_period_days", 30)

    return (
        f"{name} ({title}) brings {yoe:.1f} YOE with proven experience in {skills_text}. "
        f"Relevance score: {score*100:.1f}%. {avail} with a {notice}-day notice period."
    )


def search_top_candidates(
    candidates: List[Dict[str, Any]],
    target_skills: Optional[List[str]] = None,
    min_yoe: float = 4.0,
    max_yoe: float = 10.0,
    limit: int = 10,
    already_filtered: bool = True
) -> List[Dict[str, Any]]:
    """
    Uses a Min-Heap (priority queue) of size `limit` to find top candidates in O(N log K).
    Includes a counter to guarantee dictionary comparisons never occur.
    """
    heap: List[Tuple[float, int, str, Dict[str, Any], Dict[str, Any]]] = []
    counter = 0

    for cand in candidates:
        if not already_filtered:
            is_fake, _ = check_is_honeypot(cand)
            if is_fake:
                continue

        score, features = score_candidate(cand, target_skills, min_yoe, max_yoe)
        cid = cand.get("candidate_id", "")
        counter += 1

        entry = (score, counter, cid, cand, features)
        if len(heap) < limit:
            heapq.heappush(heap, entry)
        else:
            if score > heap[0][0]:
                heapq.heapreplace(heap, entry)

    # Sort descending by score
    sorted_top = sorted(heap, key=lambda x: x[0], reverse=True)

    results = []
    for rank, (score, _, cid, cand, features) in enumerate(sorted_top, 1):
        profile = cand.get("profile") or {}
        results.append({
            "rank": rank,
            "candidate_id": cid,
            "name": profile.get("anonymized_name", "Candidate"),
            "current_title": profile.get("current_title", "Engineer"),
            "location": profile.get("location", "N/A"),
            "years_of_experience": profile.get("years_of_experience", 0),
            "score": score,
            "matched_skills": features.get("matched_skills", []),
            "reasoning": generate_reasoning(cand, score, features)
        })

    return results
