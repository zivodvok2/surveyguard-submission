from __future__ import annotations

import json

from .llm_client import call_llm
from .models import CandidateFinding, VerifiedFinding


def verify_finding(candidate: CandidateFinding) -> VerifiedFinding:
    """LLM-based-because-it-needs-language-understanding: verification requires
    semantic reasoning about whether the evidence actually supports the claim —
    thresholds on numeric similarity scores cannot judge meaning-level conflicts.
    Falls back to a conservative "review" verdict if the API key is absent.
    """
    try:
        evidence_text = json.dumps(candidate.evidence, indent=2, default=str)
        prompt = (
            "You are an independent survey quality-control verifier. "
            "A detector flagged a candidate issue. Re-read the evidence and decide "
            "whether the issue is real.\n\n"
            f"Category: {candidate.category}\n"
            f"Claim: {candidate.claim}\n"
            f"Evidence:\n{evidence_text}\n\n"
            "Respond with a JSON object and nothing else:\n"
            "{\n"
            '  "verdict": "confirmed" | "rejected" | "review",\n'
            '  "confidence": 0.0-1.0,\n'
            '  "reason": "one sentence"\n'
            "}\n\n"
            "Verdict rules:\n"
            '- "confirmed": the evidence clearly and directly supports the claim.\n'
            '- "rejected": the evidence does not support the claim or contradicts it.\n'
            '- "review": ambiguous — a human listener should decide.\n'
            "Be conservative: prefer 'review' over 'confirmed' when the evidence is "
            "indirect. Prefer 'rejected' when a plausible alternative explanation exists."
        )
        raw = call_llm(prompt, max_tokens=256, expect_json=True)
        result = json.loads(raw)
        verdict = result.get("verdict", "review")
        if verdict not in {"confirmed", "rejected", "review"}:
            verdict = "review"
        confidence = round(max(0.0, min(1.0, float(result.get("confidence", 0.5)))), 3)
        reason = str(result.get("reason", "")).strip() or "No reason provided."
        return VerifiedFinding(
            **candidate.model_dump(),
            verdict=verdict,
            confidence=confidence,
            verifier_reason=reason,
        )
    except Exception as exc:
        return VerifiedFinding(
            **candidate.model_dump(),
            verdict="review",
            confidence=0.5,
            verifier_reason=f"Verifier LLM call failed ({type(exc).__name__}): {exc}",
        )
