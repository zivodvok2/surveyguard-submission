from __future__ import annotations

import re
from difflib import SequenceMatcher

from .models import Alignment, QuestionSpec, TranscriptSegment


STOPWORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does", "for", "from", "has", "have", "how", "i", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "were", "what", "when", "which", "who", "why", "with", "would", "you", "your"}


def tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1 and token not in STOPWORDS}


def text_similarity(expected: str, observed: str) -> float:
    expected_tokens, observed_tokens = tokens(expected), tokens(observed)
    if not expected_tokens or not observed_tokens:
        return 0.0
    recall = len(expected_tokens & observed_tokens) / len(expected_tokens)
    precision = len(expected_tokens & observed_tokens) / len(observed_tokens)
    token_score = (2 * recall * precision / (recall + precision)) if recall + precision else 0.0
    sequence = SequenceMatcher(None, " ".join(sorted(expected_tokens)), " ".join(sorted(observed_tokens))).ratio()
    return round(0.7 * token_score + 0.3 * sequence, 4)


def align_questions(questions: list[QuestionSpec], transcript: list[TranscriptSegment]) -> list[Alignment]:
    alignments: list[Alignment] = []
    cursor = 0
    for question in questions:
        best_score, best_start, best_end, best_text = 0.0, None, None, ""
        for index in range(cursor, len(transcript)):
            for width in (1, 2):
                end_index = min(len(transcript), index + width)
                observed = " ".join(segment.text for segment in transcript[index:end_index])
                score = text_similarity(question.text, observed)
                if score > best_score:
                    best_score, best_start, best_end, best_text = score, index, end_index - 1, observed
            if best_score >= 0.83:
                break
        if best_start is not None and best_score >= 0.2:
            first, last = transcript[best_start], transcript[best_end or best_start]
            alignments.append(Alignment(question_id=question.question_id, score=best_score, segment_start=best_start, segment_end=best_end, start=first.start, end=last.end, transcript=best_text))
            if best_score >= 0.38:
                cursor = (best_end or best_start) + 1
        else:
            alignments.append(Alignment(question_id=question.question_id, score=best_score))
    return alignments


def answer_after(alignment: Alignment, transcript: list[TranscriptSegment]) -> list[TranscriptSegment]:
    if alignment.segment_end is None:
        return []
    start = alignment.segment_end + 1
    return transcript[start:min(len(transcript), start + 2)]
