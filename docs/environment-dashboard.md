# Environment dashboard

Both clean and private-demo installations start in **local development**: HTTP, DEBUG=True, local media, no HSTS and email printed to the console. They receive the complete `.env.example` and a `.env` derived from it with a newly generated SECRET_KEY.

The administrator homepage shows active security flags and whether SMTP/API configuration exists. These are basic configuration checks, not a production certification. HTTPS termination, DNS, media serving, static collection/compression, backups and `python manage.py check --deploy` must be reviewed separately.

Only superusers can use the dashboard configuration editor. Missing settings show inputs; configured settings show presence only, never stored values. Clear a configured field before replacing it. SECRET_KEY cannot be cleared; deliberate rotation must be managed separately because it invalidates sessions and signed links. Environment-injected values are marked externally managed and must be changed at their source.

Saving edits the site's `.env`, not the database. Writes are whitelisted, CSRF-protected, serialized by a file lock and replaced atomically with owner-only Unix permissions. Newlines, unknown keys and invalid ports are rejected; request POST data is marked sensitive. File comments and unrelated settings are preserved.

Boolean values use switches; non-secret deployment values use editable fields. All edits and requested key resets are committed together by **Apply changes and reload**. The form revision prevents another browser window's edits from being silently overwritten. HTTPS redirects/secure cookies are blocked from HTTP sessions; the current hostname must remain allowed. Disabling DEBUG requires a strong key and a production static manifest. Security changes require explicit confirmation.

Active Django settings are not patched in-place. Local `runserver` with its default reloader watches `.env` and restarts normally; `--noreload` requires a manual restart. Environment loading preserves actual shell/service overrides but refreshes file-provided values after a reload. Host-managed settings are disabled in the dashboard.

For cPanel using Passenger, set these in the site's `.env`, then manually restart once:

```dotenv
WULVER_RESTART_MODE=passenger
WULVER_PASSENGER_APP_ROOT=/absolute/path/to/passenger/application/root
```

The root must be the Passenger application root, not necessarily `public_html`. Its `tmp` directory must be writable by the app user. The button touches `tmp/restart.txt`, which Passenger observes on subsequent requests. No shell or sudo commands are run. This marker mechanism is unit-tested; activation on the actual hosting instance still needs verification.

`WULVER_RESTART_MODE=auto` is the default and detects autoreloading `runserver`; all other servers fall back to manual restart. `WULVER_RESTART_MODE=manual` always saves without initiating a reload. Incorrect Passenger paths or permissions retain the saved `.env` and show a manual-restart warning. Restart mode/path are administrator-managed deployment settings, never arbitrary browser-supplied commands.

For real email, set credentials and select either `apps.userprofile.email_backend.CertifiEmailBackend` or `django.core.mail.backends.smtp.EmailBackend` for EMAIL_BACKEND. Merely providing a password does not enable sending while the console backend is selected. Match EMAIL_PORT and EMAIL_USE_TLS to the provider's instructions.

The dashboard does not silently switch the site to production. Prepare HTTPS, static/media serving and hosting first; then apply the appropriate settings and verify. Keep `.env` out of Git and protect full backups containing it. Basic checks are not a production security certification.

Existing alpha-generated projects may have a hardcoded console EMAIL_BACKEND appended to `config/settings.py`. Remove that final override to allow the environment-based setting earlier in the file to take effect. New installations do not contain it. Existing `.env` files are never overwritten by updating the package; merge missing examples manually.
