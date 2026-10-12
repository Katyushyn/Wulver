# Wulver pip installation — local alpha

Nothing is published to PyPI yet. This is a packaging prototype, not a production release.

## Build and install

```sh
python -m pip install build
python -m build
python -m pip install dist/wulver-0.1.0a1-py3-none-any.whl
wulver init mysite
cd mysite
python manage.py runserver
```

Run `wulver init` outside the Wulver source checkout so that local Python modules do not shadow installed modules.

The wizard asks for slash-separated Django language codes and administrator credentials. Examples: `en`, `en/uk`, `en/uk/pl`. The first code is primary; a leading slash (`/en/uk/pl`) enables the primary URL prefix. Without it the primary language has no prefix. It creates local development settings with SQLite and a console email backend. It refuses an existing target directory. On failure the partial site is retained for diagnosis, never silently deleted.

For automation, use `--languages en/uk/pl --username admin --no-input`; provide `WULVER_ADMIN_PASSWORD` through a protected environment, not as a command-line argument. The password is not written to the project and is passed to the creation subprocess via standard input.

## Ownership of files

- Installed package: applications, migrations, default configuration blueprint, system templates, admin assets and translation catalogs.
- Site directory: `config`, `.env`, SQLite database, editable templates, custom static files, uploaded media and collected static files.
- Minimum site: one system theme, a home page and a 404 template. No demo articles, authors, media or Story theme.
- `.env` contains a freshly generated secret key and has restrictive permissions on Unix.

The wheel and source archive exclude the development site's `.env`, database, media, virtual environment, Story theme and Git history.

## Audit findings and release work still required

1. Existing migrations define EN/UK columns. These are retained internally alongside selected languages; `LANGUAGES` controls enabled languages. The installer copies migration histories for translated applications into `site_migrations` and generates language additions there before migration, never writing into installed packages. Future package updates MUST reconcile these local migration histories with upstream migrations; automated update support is not yet implemented. Do not simply replace them or treat production upgrades as certified. Additional languages do not automatically translate content or Wulver-specific UI catalogs.
2. Theme uploads and edits intentionally use the site's writable `BASE_DIR/templates` and `BASE_DIR/static/themes`; system resource lookup now also includes the installed package.
3. The generic `apps` Python namespace is retained for compatibility. A dedicated namespace needs a migration/import compatibility plan before public release.
4. The AI assistant and its dependencies are included in the initial distribution by product decision. Verify safe behavior without an API key before release.
5. Database selection other than SQLite, site-name wizard options, production configuration and resumable setup remain future work.
6. Confirm the supported Python/Django/dependency matrix in clean environments, package license and redistribution permissions for vendored assets. Current pins follow the working development environment, not a certified release matrix.
7. Validate PyPI package-name availability, add final repository metadata, CI build/install tests and publish first to TestPyPI.
8. A demo installation button and distributable demo packages are a separate follow-up; demo content is not part of this installer.

Installing a new package version must not rerun bootstrap or overwrite site settings/templates. Production deployment remains separate from the development installer.
