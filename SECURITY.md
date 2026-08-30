# Security and privacy

## Deployment requirements

- Set `APP_ENV=production`.
- Set a random `JWT_SECRET` of at least 32 bytes; production startup fails when it is absent.
- Configure `ALLOWED_ORIGINS` to exact frontend origins for split deployments.
- Set bootstrap administrator credentials only for initial provisioning, then remove them.
- Store API, database, and SMTP credentials in the platform secret store, never `.env` in Git.

## Existing repository secret warning

The source repository previously contained tracked environment files. Removing them from a later commit does not invalidate credentials exposed in Git history. Rotate every key or password ever committed, remove tracked files, and rewrite history when policy requires it.

## Data handling

- Agentic source files use a unique temporary directory deleted after success or failure.
- Dataset-only temporary files expire after one hour.
- Results retain evidence text and timestamps; apply project retention rules.
- Real audio is transmitted to Groq only when transcription is requested.

## Human impact

SurveyGuard findings are QC signals, not misconduct decisions. Do not automate discipline, payment withholding, respondent exclusion, or employment decisions. A qualified reviewer must listen to consequential findings and consider project context.
