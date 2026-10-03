# Wulver

Wulver is a multilingual Django CMS focused on fast, maintainable corporate
websites. It combines structured content, editable themes and templates, SEO
controls, user accounts, comments, backups, and an extensible module model in
one administration interface.

> **Status:** pre-release. The repository is being prepared for its first
> public release. Interfaces, migrations, and installation steps may change.

## Current capabilities

- multilingual pages, blog categories, articles, and tags;
- database-managed themes, templates, and reusable template components;
- SEO metadata, Schema.org data, canonical rules, redirects, robots, and sitemap;
- image processing and article media;
- authentication, profiles, comments, contact messages, and subscriptions;
- encrypted full-site backup and restore;
- optional AI-assisted administration features;
- Django Unfold administration and Rosetta translation management.

## Local development

Requirements: Python 3.14 and the system libraries required by Pillow and the
database driver you choose.

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

For a clean starter database, the Wulver initialization command can generate
migrations, apply them, and synchronize built-in template components:

```bash
python manage.py wulver_init
```

Never commit `.env`, a local database, uploaded media, generated static files,
or backup archives. The supplied `.gitignore` excludes these runtime files.

## Production

The Django development server is not suitable for production. Deploy behind a
production WSGI/ASGI server and reverse proxy, set every security-related value
in `.env`, collect static files, and test backup restoration before launch.

Detailed installation, deployment, theme, and module documentation is planned
before the first stable release; see [the release roadmap](docs/release-roadmap.md).

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change. Report security
issues privately as described in [SECURITY.md](SECURITY.md).

## License

A redistribution license has not been selected yet. Until a license is added,
the source is not offered for redistribution. License selection is a required
task before the repository becomes public.
