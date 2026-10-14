# Security and Privacy Baseline

## Data minimization
- Store only data needed for the creator's workflow.
- Do not collect Adobe credentials, session cookies, or private account data.
- Do not send assets or metadata to an external AI service without explicit disclosure and user action.
- Make file storage and deletion behavior clear.

## Secrets
- Never commit `.env`, API keys, tokens, or passwords.
- Provide `.env.example` containing placeholders only.
- Keep secrets server-side; never place them in frontend source or Vite-exposed variables.
- If a real secret was committed, remove it from current code and rotate it. Deleting a file in a later commit does not erase Git history.

## File safety
- Restrict file operations to explicitly selected files or an application-managed directory.
- Validate extension, MIME type where available, size, and image decoding.
- Generate safe internal filenames where copying files into managed storage.
- Prevent path traversal and arbitrary file reads.
- Never automatically delete originals.

## API safety
- Validate request bodies and query parameters.
- Set upload size and request time limits.
- Use appropriate CORS rules; do not use wildcard origins with credentials.
- Avoid exposing detailed stack traces to users.
- Add authentication before exposing a multi-user deployment.
- Add rate limits to expensive AI or image-processing endpoints.

## Database and backups
- Use parameterized queries or safe ORM/query-builder APIs.
- Enable SQLite foreign-key enforcement.
- Document backup and restore.
- Avoid logging full image metadata or user content unnecessarily.

## Release checklist
- No secrets in Git status or tracked files.
- Dependencies reviewed.
- Input validation and file restrictions tested.
- Errors do not expose secrets or stack traces.
- Backup/restore process verified.
