# Contributing to Wulver

Wulver is still preparing for its first public release. Small, focused changes
with tests are preferred.

## Development workflow

1. Create a branch from the current default branch.
2. Copy `.env.example` to `.env` and use development-only credentials.
3. Install dependencies from `requirements.txt` in a virtual environment.
4. Run `python manage.py check` and `python manage.py test` before submitting.
5. Explain behavior changes, migrations, and manual verification in the pull request.

Do not commit databases, uploaded media, generated static files, backups,
credentials, API keys, production domains, or customer data. New dependencies
must have a compatible license and a clear reason for inclusion.

Translations must keep English source strings in code and templates. Update the
Ukrainian catalog when user-facing text changes.
