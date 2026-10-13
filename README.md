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

## Quick start from PyPI

Use Python 3.12 or newer (Python 3.14 is recommended). Create and activate a
virtual environment in a new directory.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install wulver
wulver init site
cd site
python manage.py runserver
```

Linux and macOS:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install wulver
wulver init site
cd site
python manage.py runserver
```

The installer asks for languages, whether to install the complete Story demo,
and administrator credentials. Both choices start with local-development
settings. Review the generated `.env` and administration dashboard before
production deployment. This is an alpha release, not a production-readiness guarantee.

## Develop from source

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

`python manage.py wulver_init` is an internal source-development command, not
the public installation workflow. New sites should be created with
`wulver init site` as shown above.

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

Original Wulver code is licensed under the [MIT License](LICENSE).
It may be used, modified, and redistributed free of charge, including for
commercial projects, subject to preserving the copyright and license notice.

The MIT license does not relicense third-party materials. The Story theme by
BootstrapMade is redistributed with the author's permission and retains its
own terms and credits. Bundled libraries, fonts, images, and other third-party
assets retain their respective licenses and notices.
