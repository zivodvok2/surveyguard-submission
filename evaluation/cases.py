from __future__ import annotations

from typing import Any


Q1 = "Compared with last month, did production increase, remain unchanged, or decrease?"
WHY = "Why did production change? PROBE FULLY"


def direction_case(case_id: str, value: int, captured_reason: str, spoken_value: str, spoken_reason: str, issues: list[tuple[str, str]], question_audio: str = Q1) -> dict[str, Any]:
    return {
        "id": case_id,
        "questionnaire": f"Q1. {Q1}\n1 = Increase\n2 = Remain unchanged\n3 = Decrease\nQ1a. {WHY}",
        "row": {"respondent_id": case_id.upper(), "Q1": value, "Q1A": captured_reason},
        "segments": [
            {"start": 0, "end": 8, "speaker": "interviewer", "text": question_audio},
            {"start": 8, "end": 13, "speaker": "respondent", "text": spoken_value},
            {"start": 13, "end": 17, "speaker": "interviewer", "text": "Why did production change?"},
            {"start": 17, "end": 25, "speaker": "respondent", "text": spoken_reason},
        ],
        "ground_truth": [{"question_id": question_id, "category": category} for question_id, category in issues],
    }


CASES: list[dict[str, Any]] = [
    direction_case("case01", 1, "Production increased because new orders arrived", "Production increased", "New customer orders arrived", []),
    direction_case("case02", 3, "Production decreased after demand weakened", "Production decreased", "Demand from regular customers weakened", []),
    direction_case("case03", 1, "Production increased because demand grew", "Production decreased", "Customer demand was lower", [("Q1", "audio_data_mismatch"), ("Q1", "verbatim_contradicts_audio")]),
    direction_case("case04", 1, "Production decreased because orders fell", "Production increased", "Several new orders arrived", [("Q1", "audio_data_mismatch")]),
    direction_case("case05", 9, "Production increased because demand grew", "Production increased", "Demand grew", [("Q1", "invalid_code")]),
    direction_case("case06", 1, "Demand", "Production increased", "Demand", [("Q1", "low_information_verbatim"), ("Q1A", "insufficient_probing")]),
    direction_case("case07", 1, "It just happened", "Production increased", "It just happened", [("Q1A", "insufficient_probing")]),
    direction_case("case08", 1, "Employee salaries increased sharply", "Production increased", "New orders raised production", [("Q1", "off_topic_verbatim"), ("Q1", "verbatim_audio_mismatch")]),
    direction_case("case09", 1, "Production increased because demand grew", "Yes, it increased", "Demand grew", [("Q1", "possible_leading_question")], question_audio=f"{Q1} So production increased, right?"),
    {
        "id": "case10",
        "questionnaire": f"Q1. {Q1}\n1 = Increase\n2 = Remain unchanged\n3 = Decrease\nQ1a. {WHY}",
        "row": {"respondent_id": "CASE10", "Q1": 2, "Q1A": "Production stayed stable"},
        "segments": [{"start": 0, "end": 12, "speaker": "interviewer", "text": "Tell me about the weather near your office"}, {"start": 12, "end": 24, "speaker": "respondent", "text": "It was sunny throughout the week"}],
        "ground_truth": [{"question_id": "Q1", "category": "question_not_detected"}, {"question_id": "Q1A", "category": "question_not_detected"}],
    },
    {
        "id": "case11",
        "questionnaire": "Q3. CONSENT: Do you agree to participate in this research interview?\n1 = Yes\n2 = No",
        "row": {"respondent_id": "CASE11", "Q3": 1},
        "segments": [{"start": 0, "end": 10, "speaker": "interviewer", "text": "What products did you buy last week?"}, {"start": 10, "end": 22, "speaker": "respondent", "text": "I bought flour and cooking oil"}],
        "ground_truth": [{"question_id": "Q3", "category": "consent_not_detected"}],
    },
    {
        "id": "case12",
        "questionnaire": "Q2. READ EXACTLY: Has the number of employees increased, remained unchanged, or decreased?\n1 = Increase\n2 = Remain unchanged\n3 = Decrease",
        "row": {"respondent_id": "CASE12", "Q2": 1},
        "segments": [{"start": 0, "end": 12, "speaker": "interviewer", "text": "Did the number of employees increase or decrease?"}, {"start": 12, "end": 22, "speaker": "respondent", "text": "The number increased"}],
        "ground_truth": [{"question_id": "Q2", "category": "required_wording_changed"}],
    },
    direction_case("case13", 2, "Production remained unchanged", "Production stayed the same", "Output was stable throughout the month", [] , question_audio="Was production up, flat, or down this month?"),
    direction_case("case14", 1, "Input costs changed after supplier delays", "Production increased because new orders arrived", "New customer orders raised output", [("Q1", "off_topic_verbatim"), ("Q1", "verbatim_audio_mismatch")]),
    direction_case("case15", 1, "Production capacity returned after a factory shutdown ended", "Production increased", "Production capacity returned after the shutdown", []),
    {
        "id": "case16",
        "questionnaire": "Q4. How satisfied are you with the service overall?\n1 = Very dissatisfied\n2 = Dissatisfied\n3 = Neutral\n4 = Satisfied\n5 = Very satisfied",
        "row": {"respondent_id": "CASE16", "Q4": 5},
        "segments": [{"start": 0, "end": 11, "speaker": "interviewer", "text": "Would you recommend the company to a friend?"}, {"start": 11, "end": 23, "speaker": "respondent", "text": "Yes, I probably would"}],
        "ground_truth": [{"question_id": "Q4", "category": "question_not_detected"}],
    },
    direction_case("case17", 3, "Production fell", "Production decreased", "Production fell", [("Q1", "low_information_verbatim")]),
    direction_case("case18", 3, "Employee salaries decreased after overtime ended", "Production decreased", "Low demand reduced production", [("Q1", "off_topic_verbatim"), ("Q1", "verbatim_audio_mismatch")]),
    direction_case("case19", 2, "Production remained stable because orders were steady", "Production was unchanged", "Orders remained steady", []),
    direction_case("case20", 1, "Production did not decrease; it increased after new orders", "Production did not decrease; it increased", "New orders arrived", []),
]
