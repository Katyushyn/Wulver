"""Environment loading and explicitly supported reload strategies; no shell."""
import json
import os
from pathlib import Path
import sys
import re

import environ
from django.conf import settings
from django.utils.autoreload import autoreload_started


def load_site_environment(path):
    # runserver's parent imports settings before spawning children. Preserve only
    # genuine service/shell overrides, not stale .env values inherited from it.
    marker = '_WULVER_EXTERNAL_ENV_KEYS'
    if marker not in os.environ:
        os.environ[marker] = json.dumps(list(os.environ))
    external = set(json.loads(os.environ[marker]))
    saved = {key: os.environ[key] for key in external if key in os.environ}
    text = Path(path).read_text() if Path(path).exists() else ''
    file_keys = set(re.findall(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=', text, re.MULTILINE))
    for key in set(json.loads(os.environ.get('_WULVER_FILE_ENV_KEYS', '[]'))) - file_keys - external:
        os.environ.pop(key, None)
    environ.Env.read_env(path, overwrite=True)
    os.environ.update(saved)
    os.environ['_WULVER_FILE_ENV_KEYS'] = json.dumps(sorted(file_keys))


def watch_environment(sender, **kwargs):
    sender.extra_files.add(Path(settings.BASE_DIR) / '.env')


autoreload_started.connect(watch_environment, dispatch_uid='wulver.watch.environment', weak=False)


def externally_managed(key):
    return key in json.loads(os.environ.get('_WULVER_EXTERNAL_ENV_KEYS', '[]'))


def restart_strategy():
    mode = getattr(settings, 'WULVER_RESTART_MODE', 'auto')
    if mode == 'auto' and 'runserver' in sys.argv and os.environ.get('RUN_MAIN') == 'true' and '--noreload' not in sys.argv:
        return 'runserver'
    if mode == 'passenger':
        return 'passenger'
    return 'manual'


def request_restart():
    mode = restart_strategy()
    if mode == 'passenger':
        raw = getattr(settings, 'WULVER_PASSENGER_APP_ROOT', '')
        if not raw or not Path(raw).is_absolute():
            raise OSError('Passenger application root must be explicitly configured as an absolute path.')
        root = Path(raw)
        if not root.is_dir() or root.is_symlink():
            raise OSError('Invalid Passenger application root.')
        directory = root / 'tmp'
        if directory.is_symlink():
            raise OSError('Unsafe Passenger restart directory.')
        directory.mkdir(exist_ok=True)
        marker = directory / 'restart.txt'
        if marker.is_symlink():
            raise OSError('Unsafe Passenger restart marker.')
        marker.touch()
    # runserver observes the atomic .env replacement through its normal reloader.
    return mode
