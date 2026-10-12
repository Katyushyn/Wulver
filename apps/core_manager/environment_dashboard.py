"""Superuser-only configuration status; secrets never enter rendered context."""
import json
import os
from pathlib import Path
import re
import shlex
import tempfile
import hashlib
import uuid
from types import MethodType

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.http import JsonResponse
from django.core import signing
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache

FIELDS = {
    'SECRET_KEY': (_('Django secret key'), True),
    'EMAIL_HOST': (_('SMTP host'), False),
    'EMAIL_BACKEND': (_('Email backend'), False),
    'EMAIL_USE_TLS': (_('SMTP TLS'), False),
    'EMAIL_PORT': (_('SMTP port'), False),
    'EMAIL_HOST_USER': (_('SMTP username'), False),
    'EMAIL_HOST_PASSWORD': (_('SMTP password'), True),
    'DEFAULT_FROM_EMAIL': (_('Sender email address'), False),
    'OPENAI_API_KEY': (_('OpenAI API key'), True),
    'GOOGLE_CLIENT_ID': (_('Google OAuth client ID'), False),
    'GOOGLE_CLIENT_SECRET': (_('Google OAuth client secret'), True),
    'ARTICLE_API_TOKEN': (_('Article API token'), True),
    'GITHUB_TOKEN': (_('GitHub token'), True),
}

BOOLEAN_FIELDS = (
    'DEBUG', 'SERVE_MEDIA_LOCALLY', 'SECURE_SSL_REDIRECT', 'SESSION_COOKIE_SECURE',
    'CSRF_COOKIE_SECURE', 'SECURE_HSTS_INCLUDE_SUBDOMAINS', 'SECURE_HSTS_PRELOAD',
    'TRUST_X_FORWARDED_PROTO', 'TRUST_X_FORWARDED_FOR', 'AI_ASSISTANT_TRUST_X_FORWARDED_FOR',
    'CSP_ENABLED', 'CSP_REPORT_ONLY', 'EMAIL_USE_TLS',
)
DEPLOYMENT_FIELDS = ('ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS', 'SECURE_HSTS_SECONDS', 'ACCOUNT_DEFAULT_HTTP_PROTOCOL')
PROCESS_TOKEN = uuid.uuid4().hex
SWITCH_GUIDANCE = {
    'SECURE_HSTS_INCLUDE_SUBDOMAINS': (_('Extend HSTS to all subdomains only when every subdomain supports HTTPS.'), 'False', _('False; True only after checking all subdomains')),
    'SECURE_HSTS_PRELOAD': (_('Enable only when deliberately preparing the domain for the browser HSTS preload list. This switch does not submit the domain.'), 'False', _('False; optional preload configuration')),
    'TRUST_X_FORWARDED_PROTO': (_('Trust the forwarded protocol only when a trusted reverse proxy overwrites this header and direct access cannot bypass it.'), 'False', _('False; True only behind a trusted HTTPS proxy')),
    'TRUST_X_FORWARDED_FOR': (_('Trust forwarded client IPs only when a trusted proxy overwrites the header. Otherwise visitors can spoof their IP.'), 'False', _('False; True only behind a trusted proxy')),
    'AI_ASSISTANT_TRUST_X_FORWARDED_FOR': (_('Use forwarded client IPs for the AI assistant under the same trusted-proxy conditions.'), 'False', _('False; True only behind a trusted proxy')),
    'CSP_ENABLED': (_('Enable Content Security Policy. Check that the policy allows the scripts, styles and external resources required by your theme.'), 'True', _('True after checking compatibility with the site')),
    'CSP_REPORT_ONLY': (_('Report CSP violations without blocking resources. Use this to test a policy before enforcing it; it has no effect when CSP is disabled.'), 'False', _('True during CSP testing; False for enforcement')),
    'EMAIL_USE_TLS': (_('Enable STARTTLS when required by your SMTP provider, commonly on port 587. Console email ignores this setting; implicit TLS on port 465 is different.'), _('True (ignored by console email)'), _('Depends on the SMTP provider; usually True for port 587')),
}


def env_values(text):
    result = {}
    for line in text.splitlines():
        match = re.match(r'^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)$', line)
        if not match:
            continue
        key, value = match.groups()
        try:
            if value.startswith('"'):
                value, _end = json.JSONDecoder().raw_decode(value)
            else:
                value = ' '.join(shlex.split(value, comments=True))
        except (ValueError, json.JSONDecodeError):
            value = ''
        result[key] = str(value)
    return result


def validate_value(key, value):
    if key not in {*FIELDS, *BOOLEAN_FIELDS, *DEPLOYMENT_FIELDS} or '\n' in value or '\r' in value or '\x00' in value or len(value) > 8192:
        raise ValidationError(_('Invalid configuration value.'))
    if key in BOOLEAN_FIELDS and value not in {'True', 'False'}:
        raise ValidationError(_('Use True or False.'))
    if key == 'SECURE_HSTS_SECONDS' and (not value.isdigit() or int(value) > 63072000):
        raise ValidationError(_('Invalid HSTS duration.'))
    if key == 'ACCOUNT_DEFAULT_HTTP_PROTOCOL' and value not in {'http', 'https'}:
        raise ValidationError(_('Use http or https.'))
    if key == 'EMAIL_PORT' and value and (not value.isdigit() or not 1 <= int(value) <= 65535):
        raise ValidationError(_('SMTP port must be between 1 and 65535.'))
    if key == 'EMAIL_USE_TLS' and value and value.lower() not in {'true', 'false'}:
        raise ValidationError(_('Use True or False.'))
    if key == 'EMAIL_BACKEND' and value and value not in {
        'django.core.mail.backends.console.EmailBackend',
        'django.core.mail.backends.smtp.EmailBackend',
        'apps.userprofile.email_backend.CertifiEmailBackend',
    }:
        raise ValidationError(_('Choose the console or SMTP email backend.'))
    if key == 'SECRET_KEY' and len(value) < 50:
        raise ValidationError(_('Use a unique secret key with at least 50 characters. It cannot be cleared.'))


def update_environment(path, key, value):
    update_environment_values(path, {key: value})


def update_environment_values(path, changes, revision=None):
    """Validate the entire batch, then lock and replace once."""
    for key, value in changes.items():
        validate_value(key, value)
    path = Path(path)
    if path.is_symlink():
        raise ValidationError(_('Editing a symlinked environment file is not supported.'))
    lock_path = path.with_name('.env.wulver.lock')
    if lock_path.is_symlink():
        raise ValidationError(_('Unsafe environment lock file.'))
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(descriptor, 'r+b') as lock:
        try:
            import fcntl
        except ImportError:
            import msvcrt
            if not lock.read(1):
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock, fcntl.LOCK_EX)
        text = path.read_text() if path.exists() else ''
        if revision and hashlib.sha256(text.encode()).hexdigest() != revision:
            raise ValidationError(_('Configuration changed in another window. Reload before applying.'))
        lines = text.splitlines()
        for key, value in changes.items():
            pattern = re.compile(r'^\s*(?:export\s+)?' + re.escape(key) + r'\s*=')
            indices = [i for i, line in enumerate(lines) if pattern.match(line)]
            replacement = key + '=' + json.dumps(value, ensure_ascii=False)
            if indices:
                lines[indices[0]] = replacement
                lines = [line for i, line in enumerate(lines) if i not in indices[1:]]
            else:
                lines.append(replacement)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.wulver-env-', delete=False) as temp:
                temp_path = Path(temp.name)
                os.chmod(temp_path, 0o600)
                temp.write('\n'.join(lines) + '\n')
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()
    # Process environment and Django settings are deliberately not mutated here.


def apply_dashboard_changes(request):
    from .environment_runtime import externally_managed
    path = Path(settings.BASE_DIR) / '.env'
    current = env_values(path.read_text()) if path.exists() else {}
    changes = {key: 'True' if request.POST.get('switch_' + key) == 'on' else 'False' for key in BOOLEAN_FIELDS if not externally_managed(key)}
    for key in DEPLOYMENT_FIELDS:
        if key in request.POST:
            changes[key] = request.POST[key].strip()
    for key in FIELDS:
        if key in BOOLEAN_FIELDS:
            continue
        if request.POST.get('clear_' + key) == 'on':
            changes[key] = ''
        elif request.POST.get('value_' + key, '').strip():
            changes[key] = request.POST['value_' + key].strip()
    for key, value in changes.items():
        if externally_managed(key):
            raise ValidationError(_('This parameter is managed by the hosting environment. Change it there.'))
        validate_value(key, value)
    proposed = {**current, **changes}
    for key in (*BOOLEAN_FIELDS, *DEPLOYMENT_FIELDS, 'SECRET_KEY'):
        if externally_managed(key):
            active = getattr(settings, key)
            proposed[key] = ','.join(active) if isinstance(active, (list, tuple)) else str(active)
    flag = lambda key: proposed.get(key, str(getattr(settings, key, False))).lower() == 'true'
    if not request.is_secure() and any(flag(key) for key in ('SECURE_SSL_REDIRECT', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE')):
        raise ValidationError(_('HTTPS settings cannot be enabled from an HTTP session. Configure HTTPS first.'))
    if not flag('DEBUG'):
        secret = proposed.get('SECRET_KEY', settings.SECRET_KEY)
        if len(secret) < 50 or secret == 'unsafe-dev-secret-key':
            raise ValidationError(_('Production requires a strong SECRET_KEY.'))
        # Switching storage to production requires a prebuilt manifest.
        if getattr(settings, 'DEBUG', False) and not (Path(settings.STATIC_ROOT) / 'staticfiles.json').is_file():
            raise ValidationError(_('Collect production static files before disabling DEBUG.'))
    hosts = [h.strip() for h in proposed.get('ALLOWED_HOSTS', ','.join(settings.ALLOWED_HOSTS)).split(',') if h.strip()]
    if not flag('DEBUG') and '*' in hosts:
        raise ValidationError(_('Production ALLOWED_HOSTS cannot contain a wildcard.'))
    from django.http.request import split_domain_port
    host = split_domain_port(request.get_host())[0].strip('[]')
    if not any(h == '*' or h == host or (h.startswith('.') and (host == h[1:] or host.endswith(h))) for h in hosts):
        raise ValidationError(_('ALLOWED_HOSTS must retain the current hostname.'))
    csrf_origins = proposed.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if any(origin.strip() and not re.fullmatch(r'https?://[^\s/]+', origin.strip()) for origin in csrf_origins):
        raise ValidationError(_('CSRF origins must contain http:// or https:// and a hostname.'))
    risks = any(changes.get(key, current.get(key)) != current.get(key, str(getattr(settings, key, ''))) for key in (
        'DEBUG', 'SECURE_SSL_REDIRECT', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE',
        'TRUST_X_FORWARDED_PROTO', 'TRUST_X_FORWARDED_FOR', 'AI_ASSISTANT_TRUST_X_FORWARDED_FOR',
        'SECURE_HSTS_INCLUDE_SUBDOMAINS', 'SECURE_HSTS_PRELOAD',
        'CSP_ENABLED', 'CSP_REPORT_ONLY', 'SECURE_HSTS_SECONDS', 'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS',
    ))
    if risks and request.POST.get('confirm_risks') != 'on':
        raise ValidationError(_('Confirm security changes before applying.'))
    revision = request.POST.get('environment_revision')
    if not revision:
        raise ValidationError(_('Reload the configuration page before applying.'))
    update_environment_values(path, changes, revision=revision)
    from .environment_runtime import request_restart
    try:
        mode = request_restart()
    except OSError:
        messages.warning(request, _('Saved, but automatic restart failed. Restart the application manually.'))
        return 'manual'
    if mode == 'manual':
        messages.warning(request, _('Saved. Automatic restart is not configured; restart the application manually.'))
    else:
        messages.success(request, _('Saved. Application reload requested; wait briefly and refresh this page.'))
    return mode


def dashboard_context():
    from .environment_runtime import externally_managed, restart_strategy
    path = Path(settings.BASE_DIR) / '.env'
    text = path.read_text() if path.exists() else ''
    values = env_values(text)
    keys = []
    for key, (label, secret) in FIELDS.items():
        if key in BOOLEAN_FIELDS:
            continue
        active = getattr(settings, key, os.environ.get(key, ''))
        # Credentials from externally managed environments remain external.
        external = externally_managed(key)
        if key == 'EMAIL_BACKEND':
            continue
        keys.append({'key': key, 'label': label, 'secret': secret,
                     'configured': bool(active) if external else bool(values.get(key)),
                     'external': external, 'clearable': key != 'SECRET_KEY' and not external})
    hosts = settings.ALLOWED_HOSTS
    checks = [
        ('DEBUG', settings.DEBUG, not settings.DEBUG),
        ('SERVE_MEDIA_LOCALLY', settings.SERVE_MEDIA_LOCALLY, not settings.SERVE_MEDIA_LOCALLY),
        ('SECURE_SSL_REDIRECT', settings.SECURE_SSL_REDIRECT, settings.SECURE_SSL_REDIRECT),
        ('SESSION_COOKIE_SECURE', settings.SESSION_COOKIE_SECURE, settings.SESSION_COOKIE_SECURE),
        ('CSRF_COOKIE_SECURE', settings.CSRF_COOKIE_SECURE, settings.CSRF_COOKIE_SECURE),
        ('SECURE_HSTS_SECONDS', settings.SECURE_HSTS_SECONDS, settings.SECURE_HSTS_SECONDS > 0),
        ('ALLOWED_HOSTS', ', '.join(hosts), bool(hosts) and '*' not in hosts and not any(h in {'localhost', '127.0.0.1'} for h in hosts)),
        ('SECRET_KEY', _('Configured') if settings.SECRET_KEY else _('Missing'),
         bool(settings.SECRET_KEY) and len(settings.SECRET_KEY) >= 50 and settings.SECRET_KEY != 'unsafe-dev-secret-key'),
    ]
    statuses = {name: {'production_checked': True, 'production_ok': bool(ok)} for name, value, ok in checks}
    for item in keys:
        item.update(statuses.get(item['key'], {}))
    guidance = {key: {'help': help_text, 'local_default': local, 'production_default': production}
                for key, (help_text, local, production) in SWITCH_GUIDANCE.items()}
    return {'environment_keys': keys,
            'environment_email_backend': values.get('EMAIL_BACKEND') or settings.EMAIL_BACKEND,
            'environment_email_backend_external': externally_managed('EMAIL_BACKEND'),
            'environment_smtp_backend': 'apps.userprofile.email_backend.CertifiEmailBackend' if (values.get('EMAIL_BACKEND') or settings.EMAIL_BACKEND) == 'apps.userprofile.email_backend.CertifiEmailBackend' else 'django.core.mail.backends.smtp.EmailBackend',
            'environment_revision': hashlib.sha256(text.encode()).hexdigest(),
            'environment_restart_mode': restart_strategy(),
            'environment_switches': [{'key': key, **statuses.get(key, {}), **guidance.get(key, {}), 'external': externally_managed(key), 'enabled': (str(getattr(settings, key, False)) if externally_managed(key) else values.get(key, str(getattr(settings, key, False)))).lower() == 'true'} for key in BOOLEAN_FIELDS],
            'environment_deployment_fields': [{'key': key, **statuses.get(key, {}), 'external': externally_managed(key), 'value': (','.join(getattr(settings, key)) if key in {'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS'} else str(getattr(settings, key))) if externally_managed(key) else values.get(key, ','.join(getattr(settings, key)) if key in {'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS'} else str(getattr(settings, key)))} for key in DEPLOYMENT_FIELDS],
            'environment_checks': [{'name': name, 'value': value, 'ok': bool(ok)} for name, value, ok in checks],
            'environment_local': settings.DEBUG,
            'environment_basic_ready': all(ok for _, _, ok in checks),
            'environment_mail_console': settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend',
            'environment_exists': path.exists()}


def activity_context(request, site):
    """Bounded, permission-aware summaries; never render private log payloads."""
    from django.apps import apps
    specifications = (
        ('core_manager', 'ContactMessage', _('Contact messages'), 'created_at', 'subject', 'message'),
        ('django_comments', 'Comment', _('Comments'), 'submit_date', 'user_name', 'comment'),
        ('socialaccount', 'SocialAccount', _('Social network users'), 'date_joined', 'provider', None),
        ('core_manager', 'NewsletterSubscription', _('Newsletter subscriptions'), 'created_at', 'email', None),
        ('ai_assistant', 'AssistantEventLog', _('AI assistant logs'), 'created_at', 'event_type', 'message'),
        ('ai_assistant', 'Lead', _('Leads'), 'created_at', 'name', 'message'),
    )
    panels = []
    for app_label, model_name, title, date_field, heading, excerpt in specifications:
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        model_admin = site._registry.get(model)
        if model_admin is None or not model_admin.has_view_permission(request):
            continue
        prefix = f'admin:{model._meta.app_label}_{model._meta.model_name}'
        queryset = model_admin.get_queryset(request).order_by('-' + date_field, '-pk')
        panel = {'title': title, 'count': queryset.count(), 'url': reverse(prefix + '_changelist')}
        attention = {
            'ContactMessage': ({'is_read': False}, _('Unread messages'), '?is_read__exact=0'),
            'Comment': ({'is_public': False, 'is_removed': False}, _('Awaiting moderation'), '?is_public__exact=0&is_removed__exact=0'),
            'Lead': ({'status': 'new'}, _('New leads'), '?status__exact=new'),
        }.get(model_name)
        if attention:
            filters, label, query = attention
            panel.update(attention_count=queryset.filter(**filters).count(), attention_label=label,
                         attention_url=panel['url'] + query)
        else:
            from .models import DashboardReadState
            state = DashboardReadState.objects.filter(user=request.user, model_label=model._meta.label_lower).first()
            unseen = queryset.filter(**{date_field + '__gt': state.seen_until}) if state else queryset
            panel.update(attention_count=unseen.count(), attention_label=_('Not yet reviewed'),
                         attention_url=panel['url'],
                         seen_token=signing.dumps({'user': request.user.pk, 'model': model._meta.label_lower,
                                                  'until': timezone.now().isoformat()}, salt='dashboard-seen'))
        panels.append(panel)
    return panels


def overview_context(request, site):
    from django.apps import apps
    from wulver import __version__
    context = {'wulver_version': __version__}
    try:
        from apps.analytics_manager.dashboard import analytics_dashboard_context
        context['analytics_overview'] = analytics_dashboard_context(request, site)
    except LookupError:
        context['analytics_overview'] = None
    try:
        model = apps.get_model('backup_manager', 'BackupSnapshot')
    except LookupError:
        return context
    model_admin = site._registry.get(model)
    if model_admin and model_admin.has_view_permission(request):
        queryset = model_admin.get_queryset(request)
        latest = queryset.order_by('-created_at').first()
        last_success = queryset.filter(status='completed').order_by('-completed_at', '-created_at').first()
        context['overview_backups'] = {
            'latest': latest, 'last_success': last_success,
            'url': reverse('admin:backup_manager_backupsnapshot_changelist'),
            'create_url': reverse('admin:backup_manager_backupsnapshot_create_full') if model_admin.has_add_permission(request) else None,
        }
    return context


def install_environment_dashboard():
    site = admin.site
    if getattr(site, '_wulver_environment_dashboard', False):
        return
    original = site.index

    @method_decorator(never_cache)
    @method_decorator(sensitive_post_parameters())
    @method_decorator(csrf_protect)
    def index(self, request, extra_context=None):
        if request.method == 'POST':
            if request.POST.get('environment_action') == 'mark_seen':
                try:
                    data = signing.loads(request.POST.get('seen_token', ''), salt='dashboard-seen', max_age=86400)
                    from django.apps import apps
                    model = apps.get_model(data['model'])
                    model_admin = self._registry.get(model)
                    if data['user'] != request.user.pk or data['model'] not in {
                        'socialaccount.socialaccount', 'core_manager.newslettersubscription', 'ai_assistant.assistanteventlog'
                    } or model_admin is None or not model_admin.has_view_permission(request):
                        raise PermissionDenied
                    from .models import DashboardReadState
                    until = parse_datetime(data['until'])
                    if until is None:
                        raise PermissionDenied
                    state, created = DashboardReadState.objects.get_or_create(
                        user=request.user, model_label=data['model'], defaults={'seen_until': until})
                    if not created:
                        DashboardReadState.objects.filter(pk=state.pk, seen_until__lt=until).update(seen_until=until)
                except (signing.BadSignature, KeyError, LookupError, ValueError):
                    raise PermissionDenied
                return redirect(reverse('admin:index'))
            if not request.user.is_superuser:
                raise PermissionDenied
            key = request.POST.get('environment_key', '')
            action = request.POST.get('environment_action', '')
            if action == 'apply':
                mode = 'manual'
                try:
                    mode = apply_dashboard_changes(request)
                except ValidationError as exc:
                    messages.error(request, '; '.join(exc.messages))
                except OSError:
                    messages.error(request, _('Cannot write .env. Check file permissions.'))
                return redirect(reverse('admin:index') + ('?environment_reload=1&previous_process=' + PROCESS_TOKEN if mode in {'runserver', 'passenger'} else ''))
            if key not in FIELDS or action not in {'save', 'clear'}:
                raise PermissionDenied
            try:
                value = '' if action == 'clear' else request.POST.get('environment_value', '').strip()
                update_environment(Path(settings.BASE_DIR) / '.env', key, value)
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
            except OSError:
                messages.error(request, _('Cannot write .env. Check file permissions.'))
            else:
                messages.success(request, _('Saved to .env. Restart all application processes to apply changes.'))
            return redirect(reverse('admin:index'))
        context = dict(extra_context or {})
        context['title'] = _('Site overview')
        context.update(overview_context(request, self))
        from .dashboard_health import dashboard_health_context
        context['dashboard_health'] = dashboard_health_context(
            request,
            refresh=request.GET.get('health_refresh') == '1',
        )
        context['activity_panels'] = activity_context(request, self)
        if request.user.is_superuser:
            if request.GET.get('environment_probe') == '1':
                return JsonResponse({'process': PROCESS_TOKEN})
            context.update(dashboard_context())
            context['environment_refresh_after_reload'] = request.GET.get('environment_reload') == '1'
        response = original(request, extra_context=context)
        response.template_name = 'admin/core_manager/environment_index.html'
        return response

    site.index = MethodType(index, site)
    site._wulver_environment_dashboard = True
