# GitHub repository setup (phone-friendly)

## Create the repository
1. Open https://github.com/new while signed into the intended GitHub account.
2. Repository name: `PulseGrid-Health`.
3. Description: `Population and workforce health intelligence platform`.
4. Choose **Private** during development.
5. Do not initialise with a README, licence, or `.gitignore` if uploading this
   prepared scaffold as the initial repository contents.
6. Create repository.

## Upload scaffold
1. Download and extract `pulsegrid-health-phase1.zip`.
2. Open the new repository on GitHub.
3. Select **Add file → Upload files**.
4. Upload the extracted folder contents (not the ZIP itself).
5. Commit to `main` with message `chore: initialise PulseGrid Phase 1 foundation`.
6. Confirm that `.github/workflows/ci.yml`, `apps/`, `database/`, `datasets/`,
   `docs/`, and `scripts/` appear in the repository.

If GitHub mobile upload is difficult, use github.dev:
- Open the repository.
- Press `.` (period) on a desktop keyboard, or open the repository in github.dev.
- Use the file explorer to create or upload files.
- Commit and push from Source Control.

## Repository settings
- Keep repository private until security review.
- Enable Issues and Discussions only if needed.
- Add branch protection for `main`: require pull requests and passing CI.
- Enable secret scanning and push protection if available.
- Never paste `.env` values into issues, commits, screenshots, or chat.

## First verification
- Open Actions and confirm the CI workflow is detected.
- A first CI failure is not evidence of a successful setup; inspect and fix it.
- Add `DATABASE_URL` only as a GitHub Actions secret when a database-backed
  integration workflow is introduced. The current unit tests do not require it.
- Do not add real health records.

## Current scaffold limitations
This starter contains the first migration and in-memory validation/detection
services. The CSV endpoint validates but explicitly does not persist rows yet.
Database persistence, complete auth/RBAC, tenant isolation, alert review UI,
and production deployment are subsequent implementation tasks.
