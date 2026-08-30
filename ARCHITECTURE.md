# Architecture

## Design principle

Use deterministic code wherever the answer is objective; use model reasoning only where language or audio meaning is required; verify every semantic candidate against the original evidence before presenting it.

## Components and contracts

### Questionnaire agent

Input: questionnaire file. Output: `QuestionSpec[]` containing question ID, text, codes, paired reason variable, read-exactly/read-options/probe/consent instructions, and routing hints.

The built-in extractor is deterministic and reproducible. It supports optional PDF/DOCX text extraction. This makes the evaluation independent of a proprietary model while retaining a structured agent boundary that can later use an LLM extractor.

### Deterministic QC engine

Input: cleaned dataframe + configuration. Output: typed checks with name, issue type, severity, flag count, rows, message, and evidence.

It owns missing values, invalid ranges, duplicates, logic, patterns, duration, straightlining, eligibility, and repeated combinations. An LLM is not asked to calculate these facts.

### Transcription tool

Input: completed recording or timestamped transcript. Output: `TranscriptSegment[]` with start, end, text, and speaker.

Groq Whisper is used only when real audio is supplied. JSON/SRT/VTT/TXT makes every code path reproducible without credentials. Provider output without speakers remains `unknown`; SurveyGuard does not infer identities.

### Alignment agent

Input: `QuestionSpec[]` + `TranscriptSegment[]`. Output: ordered question-to-segment alignments with timestamps and similarity evidence.

Similarity combines token F1 and sequence similarity. Alignment stays ordered to reduce matching a later repeated word to an earlier question.

### Semantic detector

Input: one question spec, aligned audio, captured row, and questionnaire codes. Output: recall-biased candidate findings.

### Independent verifier

Input: candidate claim + original evidence only. Output: `confirmed`, `review`, or `rejected`, with its own confidence and a concise evidence reason.

The detector is intentionally broader than the verifier. On the submitted benchmark, the unverified detector produced two false positives; the verifier rejected both, raising precision from 0.909 to 1.000.

### Human review and report

The reviewer can confirm, reject, or mark a finding for investigation. Excel export includes the rule specification, every finding, verifier reason, timestamps, and transcript evidence.

## State and data lifecycle

- Dataset-only uploads use an in-memory ID and temporary server file with a one-hour TTL.
- Multimodal audits use an isolated temporary directory deleted after completion or failure.
- Results contain bounded evidence snippets rather than source recordings.
- Jobs are in-memory for the hackathon deployment. A production queue/object store is the clear scale-out path.

## Failure modes

| Failure | Behaviour |
|---|---|
| Unsupported file | 415 with accepted format guidance |
| Oversized file | 413; 150 MB per-file limit |
| No questionnaire questions extracted | Audit fails with explicit error |
| Real audio without model key | Audit fails; transcript formats remain available |
| Weak question match | Candidate goes to verifier; plausible paraphrases can be rejected |
| Ambiguous semantic evidence | `review`, never automatic failure |
| Provider error | Generic upstream error; keys/provider bodies are not exposed |
| Audit exception | Job becomes `failed`; temporary files are deleted |

## Deployment

The Docker image has a Node 20 build stage and Python 3.11 runtime stage. The runtime installs ffmpeg for media metadata, builds the React app from source, and runs as a non-root user. FastAPI serves both `/api` and the built SPA from one origin.
