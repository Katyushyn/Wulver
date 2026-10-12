"""Create a new isolated site; never overwrite an existing project."""
import argparse
from getpass import getpass
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import re
import unicodedata

from .paths import RESOURCES_DIR, APPS_DIR
from . import __version__

from django.conf.locale import LANG_INFO

TRANSLATED_APPS = ('core_manager', 'blog_manager', 'comments_manager', 'userprofile')


def parse_languages(value):
    """A leading slash enables the primary language URL prefix."""
    prefix = value.startswith('/')
    codes = value[1:].split('/') if prefix else value.split('/')
    codes = [code.strip().lower() for code in codes]
    if not codes or any(code not in LANG_INFO for code in codes):
        raise ValueError('Use supported Django language codes, for example en/uk/pl or /en/uk/pl.')
    if len(set(codes)) != len(codes):
        raise ValueError('Each language must appear only once.')
    return codes, prefix


def ask_demo():
    while True:
        raw = input('Install full Story demo (theme, templates, authors, articles and images)? [y/N]: ')
        # Pasting from terminals can include ANSI/bracketed-paste sequences,
        # invisible formatting characters or full-width digits.
        value = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', raw)
        value = unicodedata.normalize('NFKC', value)
        value = ''.join(c for c in value if unicodedata.category(c) not in {'Cf', 'Cc', 'Cs'})
        value = value.strip().strip('`\"\'').strip().casefold()
        if value in {'y', 'у', 'yes', 'так', '1'}:
            return True
        if value in {'', '2', 'n', 'т', 'no', 'ні', 'н', '0'}:
            return False
        print(f'Unrecognized input: {raw!r}. Enter y for the full demo or n for a clean site (Enter = no).')


def run(project, *args):
    subprocess.run([sys.executable, 'manage.py', *args], cwd=project, check=True,
                   env=project_environment())


def project_environment():
    environment = os.environ.copy()
    environment['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    environment.pop('WULVER_ADMIN_PASSWORD', None)
    return environment


def main(argv=None):
    parser = argparse.ArgumentParser(description='Create a clean Wulver site.')
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('directory', help='New project directory.')
    init.add_argument('--languages', help='en/uk/pl: no primary prefix; /en/uk/pl: all languages prefixed')
    init.add_argument('--username')
    init.add_argument('--demo', action=argparse.BooleanOptionalAction, default=None,
                      help='Install the private demonstration, if included in this build.')
    init.add_argument('--no-input', action='store_true')
    init.add_argument('--allow-weak-password', action='store_true',
                      help='Explicitly bypass password validation for local development.')
    args = parser.parse_args(argv)
    project = Path(args.directory).resolve()
    if project.exists():
        parser.error('The destination already exists. Choose a new directory.')
    if not (RESOURCES_DIR / 'project' / 'settings.py').is_file():
        parser.error('Install the built Wulver wheel first; resource bundle is missing.')
    if not args.no_input and not args.languages:
        print('First language is primary. Examples:')
        print('  en        — one language; primary URL prefix OFF')
        print('  en/uk     — two languages; primary URL prefix OFF')
        print('  en/uk/pl  — three languages; primary URL prefix OFF')
        print('  /en, /en/uk, /en/uk/pl — same choices; primary URL prefix ON')
    value = args.languages or ('en' if args.no_input else input('Languages [en]: ').strip() or 'en')
    try:
        selected, prefix = parse_languages(value)
    except ValueError as exc:
        parser.error(str(exc))
    language = selected[0]
    demo = args.demo
    if demo is None:
        demo = False if args.no_input else ask_demo()
    if demo and not (RESOURCES_DIR / 'demo' / 'story.zip').is_file():
        parser.error('Demo is not included in this build. Use the private review build or choose no demo.')
    print('Installation: FULL STORY DEMO' if demo else 'Installation: CLEAN SITE (no demo)')
    print('Profile: LOCAL DEVELOPMENT (DEBUG=True, HTTP, console email). Configure production before deployment.')
    username = args.username or ('admin' if args.no_input else input('Administrator username [admin]: ').strip() or 'admin')
    password = os.environ.get('WULVER_ADMIN_PASSWORD')
    if not password and not args.no_input:
        password = getpass('Administrator password: ')
        if password != getpass('Confirm password: '):
            parser.error('Passwords do not match.')
    if not password:
        parser.error('Supply an administrator password (WULVER_ADMIN_PASSWORD in noninteractive mode).')
    from django.contrib.auth.password_validation import validate_password
    from django.conf import settings
    settings.configure(AUTH_PASSWORD_VALIDATORS=[
        {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
        {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
        {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    ], USE_I18N=False)
    from django.core.exceptions import ValidationError
    try:
        validate_password(password)
    except ValidationError as exc:
        print('Password warning: ' + '; '.join(exc.messages), file=sys.stderr)
        allowed = args.allow_weak_password
        if not allowed and not args.no_input:
            allowed = input('Use this weak password for local development anyway? [y/N]: ').strip().lower() in {'y', 'yes'}
        if not allowed:
            parser.error('Choose a stronger password, or explicitly confirm a local-development password.')
    project.mkdir(parents=True)
    for folder in ('config', 'templates', 'static', 'media', 'locale'):
        (project / folder).mkdir()
    (project / 'config' / '__init__.py').touch()
    for name in ('settings.py', 'urls.py', 'wsgi.py', 'asgi.py'):
        shutil.copy2(RESOURCES_DIR / 'project' / name, project / 'config' / name)
    with (project / 'config' / 'settings.py').open('a') as stream:
        stream.write('\n# Installation choices: translation schema stays stable across sites.\n')
        stream.write(f'LANGUAGE_CODE = {language!r}\nLANGUAGES = {tuple((code, LANG_INFO[code]["name_local"]) for code in selected)!r}\n')
        fallback = tuple(dict.fromkeys([language, 'en', 'uk'])) if demo else (language,)
        stream.write(f'MODELTRANSLATION_DEFAULT_LANGUAGE = {language!r}\nMODELTRANSLATION_FALLBACK_LANGUAGES = {fallback!r}\n')
        stream.write(f'MODELTRANSLATION_LANGUAGES = {tuple(dict.fromkeys(["en", "uk", *selected]))!r}\n')
        stream.write(f'PREFIX_DEFAULT_LANGUAGE = {prefix!r}\n')
        stream.write('OG_LOCALE_BY_LANGUAGE = {code: code.replace("-", "_") for code, _ in LANGUAGES}\n')
        stream.write(f'MIGRATION_MODULES = {dict((app, "site_migrations." + app) for app in TRANSLATED_APPS)!r}\n')
    env_example = (RESOURCES_DIR / 'project' / 'env.example').read_text()
    (project / '.env.example').write_text(env_example)
    (project / '.env').write_text(env_example.replace('SECRET_KEY=\n', f'SECRET_KEY={secrets.token_urlsafe(48)}\n', 1))
    (project / '.env').chmod(0o600)
    (project / '.gitignore').write_text('.env\n.venv/\n*.sqlite3\nmedia/\nstaticfiles/\ncaches/\n__pycache__/\n')
    (project / 'manage.py').write_text('import os, sys\nos.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")\nfrom django.core.management import execute_from_command_line\nexecute_from_command_line(sys.argv)\n')
    (project / 'requirements.txt').write_text(f'wulver=={__version__}\n')
    migration_root = project / 'site_migrations'
    migration_root.mkdir()
    (migration_root / '__init__.py').touch()
    for app in TRANSLATED_APPS:
        shutil.copytree(APPS_DIR / app / 'migrations', migration_root / app,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    try:
        run(project, 'makemigrations', *TRANSLATED_APPS, '--noinput')
        run(project, 'migrate', '--noinput')
        payload = json.dumps({'username': username, 'password': password})
        subprocess.run([sys.executable, 'manage.py', 'shell', '-c',
            'import sys,json; from django.contrib.auth import get_user_model; '
            'get_user_model().objects.create_superuser(**json.load(sys.stdin))'],
            cwd=project, input=payload, text=True, check=True, env=project_environment())
        run(project, 'wulver_install_demo' if demo else 'wulver_bootstrap')
        run(project, 'collectstatic', '--noinput', '--verbosity', '0')
        run(project, 'check')
    except subprocess.CalledProcessError:
        print(f'Initialization failed. Partial project retained at {project}; no existing site was changed.', file=sys.stderr)
        return 1
    print(f'Created {project}. Run: cd {project} && {sys.executable} manage.py runserver')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
