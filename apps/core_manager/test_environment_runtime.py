import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from .environment_runtime import load_site_environment, restart_strategy, request_restart, watch_environment


class EnvironmentRuntimeTests(SimpleTestCase):
    def test_file_values_reload_but_external_values_remain(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'EXTERNAL_TEST': 'shell'}, clear=True):
            path = Path(directory) / '.env'
            path.write_text('RELOAD_TEST=old\nEXTERNAL_TEST=file\n')
            load_site_environment(path)
            self.assertEqual(os.environ['EXTERNAL_TEST'], 'shell')
            path.write_text('EXTERNAL_TEST=changed\n')
            load_site_environment(path)
            self.assertNotIn('RELOAD_TEST', os.environ)
            path.write_text('RELOAD_TEST=new\nEXTERNAL_TEST=changed\n')
            load_site_environment(path)
            self.assertEqual(os.environ['RELOAD_TEST'], 'new')
            self.assertEqual(os.environ['EXTERNAL_TEST'], 'shell')

    def test_runserver_and_manual(self):
        with override_settings(WULVER_RESTART_MODE='auto'), patch('sys.argv', ['manage.py', 'runserver']), patch.dict(os.environ, {'RUN_MAIN': 'true'}):
            self.assertEqual(restart_strategy(), 'runserver')
        with override_settings(WULVER_RESTART_MODE='manual'):
            self.assertEqual(request_restart(), 'manual')

    def test_passenger_marker(self):
        with TemporaryDirectory() as directory, override_settings(WULVER_RESTART_MODE='passenger', WULVER_PASSENGER_APP_ROOT=directory):
            self.assertEqual(request_restart(), 'passenger')
            self.assertTrue((Path(directory) / 'tmp/restart.txt').is_file())

    def test_invalid_passenger_path(self):
        with override_settings(WULVER_RESTART_MODE='passenger', WULVER_PASSENGER_APP_ROOT=''):
            with self.assertRaises(OSError):
                request_restart()
