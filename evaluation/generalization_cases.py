from __future__ import annotations

from typing import Any


# Ten new cases covering the same issue categories as cases.py but using
# different question wording, different synonyms for directional language,
# different leading-question phrasings, and different vague-answer phrasings.
# No phrase from cases.py is reused verbatim.

Q_ORDERS = "Compared with the previous quarter, did order volumes go up, stay flat, or go down?"
Q_ORDERS_WHY = "What drove that change in orders? PROBE UNTIL FULLY EXPLAINED"
Q_CONSENT = "CONSENT: Are you willing to take part in this survey?"
Q_EMPLOYEES = "READ EXACTLY: Has your headcount expanded, held steady, or contracted?"


def _case(case_id: str, questionnaire: str, row: dict, segments: list[dict], issues: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "id": case_id,
        "questionnaire": questionnaire,
        "row": {"respondent_id": case_id.upper(), **row},
        "segments": segments,
        "ground_truth": [{"question_id": q, "category": c} for q, c in issues],
    }


def _orders_qs() -> str:
    return (
        f"Q2. {Q_ORDERS}\n"
        "1 = Went up\n"
        "2 = Stayed flat\n"
        "3 = Went down\n"
        f"Q2a. {Q_ORDERS_WHY}"
    )


GENERALIZATION_CASES: list[dict[str, Any]] = [
    # GEN01 — audio_data_mismatch: respondent says "shot up" (increase synonym)
    # but captured code is 3 (went down).
    _case(
        "gen01",
        _orders_qs(),
        {"Q2": 3, "Q2A": "Order volumes fell sharply after a key client left"},
        [
            {"start": 0, "end": 8, "speaker": "interviewer", "text": Q_ORDERS},
            {"start": 8, "end": 13, "speaker": "respondent", "text": "They shot up actually, new contracts came in"},
            {"start": 13, "end": 17, "speaker": "interviewer", "text": Q_ORDERS_WHY},
            {"start": 17, "end": 25, "speaker": "respondent", "text": "Several new contracts came in during the quarter"},
        ],
        [("Q2", "audio_data_mismatch"), ("Q2", "verbatim_contradicts_audio")],
    ),

    # GEN02 — verbatim_contradicts_audio: verbatim says "plummeted" (decrease)
    # but respondent said "surged" (increase), code=1.
    _case(
        "gen02",
        _orders_qs(),
        {"Q2": 1, "Q2A": "Orders plummeted as demand weakened"},
        [
            {"start": 0, "end": 8, "speaker": "interviewer", "text": Q_ORDERS},
            {"start": 8, "end": 13, "speaker": "respondent", "text": "Surged — we had a very strong quarter"},
            {"start": 13, "end": 17, "speaker": "interviewer", "text": Q_ORDERS_WHY},
            {"start": 17, "end": 25, "speaker": "respondent", "text": "Demand was very high from new markets"},
        ],
        [("Q2", "verbatim_contradicts_audio")],
    ),

    # GEN03 — possible_leading_question: interviewer uses assumptive framing
    # "I take it orders held steady, yes?" — none of the markers in cases.py.
    _case(
        "gen03",
        _orders_qs(),
        {"Q2": 2, "Q2A": "Output was roughly the same as before"},
        [
            {"start": 0, "end": 10, "speaker": "interviewer", "text": f"{Q_ORDERS} I take it they held steady, yes?"},
            {"start": 10, "end": 15, "speaker": "respondent", "text": "Yes, more or less"},
            {"start": 15, "end": 19, "speaker": "interviewer", "text": Q_ORDERS_WHY},
            {"start": 19, "end": 27, "speaker": "respondent", "text": "No major shifts in client base or demand"},
        ],
        [("Q2", "possible_leading_question")],
    ),

    # GEN04 — insufficient_probing: respondent says "various factors"
    # (vague but not in cases.py's literal list).
    _case(
        "gen04",
        _orders_qs(),
        {"Q2": 1, "Q2A": "Various factors"},
        [
            {"start": 0, "end": 8, "speaker": "interviewer", "text": Q_ORDERS},
            {"start": 8, "end": 13, "speaker": "respondent", "text": "They went up"},
            {"start": 13, "end": 17, "speaker": "interviewer", "text": Q_ORDERS_WHY},
            {"start": 17, "end": 21, "speaker": "respondent", "text": "Various factors"},
        ],
        [("Q2A", "insufficient_probing")],
    ),

    # GEN05 — question_not_detected: interviewer talks about something
    # completely unrelated (logistics delays) instead of asking about orders.
    _case(
        "gen05",
        _orders_qs(),
        {"Q2": 1, "Q2A": "New client relationships boosted volumes"},
        [
            {"start": 0, "end": 10, "speaker": "interviewer", "text": "Have you experienced any logistics delays recently?"},
            {"start": 10, "end": 20, "speaker": "respondent", "text": "A few minor ones but nothing serious"},
        ],
        [("Q2", "question_not_detected"), ("Q2A", "question_not_detected")],
    ),

    # GEN06 — consent_not_detected: interviewer asks about brand preferences
    # instead of the consent question.
    _case(
        "gen06",
        f"Q5. {Q_CONSENT}\n1 = Yes\n2 = No",
        {"Q5": 1},
        [
            {"start": 0, "end": 9, "speaker": "interviewer", "text": "Which brands do you buy most often?"},
            {"start": 9, "end": 18, "speaker": "respondent", "text": "Mostly store-brand products these days"},
        ],
        [("Q5", "consent_not_detected")],
    ),

    # GEN07 — required_wording_changed: READ EXACTLY question paraphrased as
    # "Did you hire or let people go?" instead of the specified wording.
    _case(
        "gen07",
        f"Q6. {Q_EMPLOYEES}\n1 = Expanded\n2 = Held steady\n3 = Contracted",
        {"Q6": 2},
        [
            {"start": 0, "end": 10, "speaker": "interviewer", "text": "Did you hire more people or let some go during the quarter?"},
            {"start": 10, "end": 18, "speaker": "respondent", "text": "We kept headcount the same"},
        ],
        [("Q6", "required_wording_changed")],
    ),

    # GEN08 — clean case: respondent clearly says "climbed" (increase synonym),
    # code=1 (went up) — no issue.
    _case(
        "gen08",
        _orders_qs(),
        {"Q2": 1, "Q2A": "Strong seasonal demand lifted volumes"},
        [
            {"start": 0, "end": 8, "speaker": "interviewer", "text": Q_ORDERS},
            {"start": 8, "end": 13, "speaker": "respondent", "text": "Climbed considerably over the quarter"},
            {"start": 13, "end": 17, "speaker": "interviewer", "text": Q_ORDERS_WHY},
            {"start": 17, "end": 25, "speaker": "respondent", "text": "Seasonal peak drove strong demand from retailers"},
        ],
        [],
    ),

    # GEN09 — possible_leading_question with "surely not?" framing
    # (different from any marker in cases.py).
    _case(
        "gen09",
        _orders_qs(),
        {"Q2": 3, "Q2A": "Order levels dropped after a major contract ended"},
        [
            {"start": 0, "end": 10, "speaker": "interviewer", "text": f"{Q_ORDERS} Surely they didn't go up, did they?"},
            {"start": 10, "end": 15, "speaker": "respondent", "text": "No, they dropped"},
            {"start": 15, "end": 19, "speaker": "interviewer", "text": Q_ORDERS_WHY},
            {"start": 19, "end": 27, "speaker": "respondent", "text": "A major long-term contract ended in the quarter"},
        ],
        [("Q2", "possible_leading_question")],
    ),

    # GEN10 — insufficient_probing: respondent says "hard to say" (not in
    # cases.py's literal vague-answer set) when probing is required.
    _case(
        "gen10",
        _orders_qs(),
        {"Q2": 2, "Q2A": "Hard to say"},
        [
            {"start": 0, "end": 8, "speaker": "interviewer", "text": Q_ORDERS},
            {"start": 8, "end": 13, "speaker": "respondent", "text": "Stayed about flat"},
            {"start": 13, "end": 17, "speaker": "interviewer", "text": Q_ORDERS_WHY},
            {"start": 17, "end": 21, "speaker": "respondent", "text": "Hard to say"},
        ],
        [("Q2A", "insufficient_probing")],
    ),
]
