# Story demo — distribution and installer notes

The Wulver maintainer confirmed on 2026-10-13 that permission to redistribute Story has been obtained from its author. The theme assets and adapted templates are included in the Wulver repository. Story design remains credited to BootstrapMade in the footer; preserve the author's credits and bundled third-party notices. This permission does not relicense Story or its dependencies under a future Wulver license.

## Build explicitly

Export from the dedicated Story demonstration database, using a new output filename:

```sh
python manage.py wulver_export_story /private/tmp/wulver-story-review.zip
WULVER_PRIVATE_DEMO=/private/tmp/wulver-story-review.zip python -m build --wheel --no-isolation --outdir private-dist
```

`private-dist/` is ignored by Git. Normal builds do not include Story; the build hook removes any previously staged demo ZIP before deciding whether to include one. A private wheel is built directly from the local source, not via a source archive. The bundle remains outside the repository.

## Install

```sh
python -m pip install --force-reinstall --no-deps /absolute/path/private-dist/wulver-0.1.0a3-py3-none-any.whl
wulver init story-demo
```

Use `--no-deps` only when the clean distribution and all dependencies are already installed. For a fresh environment install the private wheel normally with dependencies.

The wizard asks `[y/N]`: `y` installs Story; `n` or Enter installs the minimal system site. Pasted ANSI sequences and invisible formatting characters are normalized. Automation uses `--demo` or `--no-demo`.

## Included and excluded

- Story theme, 11 templates, all original theme static resources and preserved credits.
- Pages, categories, articles, images, tags, article/tag/comment/image module definitions and relations, comments and comment templates.
- Authors with avatars and unusable passwords. The original administrator is mapped to the newly created local administrator; credentials are never exported.
- Relevant site/authentication/sitemap settings and EN/UK content. Other selected languages fall back to existing demo translations, not automatic translation.
- No source passwords, sessions, permission groups, API keys, AI conversations/leads, contact messages, subscribers, backup settings or archives.
- Domain, contact identity and analytics/review integration values are cleared in the exported SiteSettings; original settings are not changed.

The importer refuses an existing theme/article dataset and refuses overwriting destination files. It imports only bundled demo records, maps authors and comment content types to the target database, and rolls back newly written files and database records on import failure.

Keep the author's permission with the project's licensing records. Review the separate licenses of bundled third-party assets and photos when preparing release packages. Publishing these source files does not automatically change the existing opt-in demo packaging workflow.
