import unittest
from unittest.mock import patch
from .cli import parse_languages, ask_demo


class LanguageSelectionTests(unittest.TestCase):
    def test_demo_choice(self):
        for answer in ('y', 'у', 'yes', 'так', '1', '１', '\x1b[200~y\x1b[201~', '\u200by\u200b', '`y`', '\udcd0y'):
            with patch('builtins.input', return_value=answer):
                self.assertTrue(ask_demo())
        with patch('builtins.input', side_effect=['maybe', 'y']):
            self.assertTrue(ask_demo())
        with patch('builtins.input', return_value=''):
            self.assertFalse(ask_demo())
        for answer in ('n', 'N', 'no', ''):
            with patch('builtins.input', return_value=answer):
                self.assertFalse(ask_demo())

    def test_examples(self):
        for value, codes in [('en', ['en']), ('en/uk', ['en', 'uk']), ('en/uk/pl', ['en', 'uk', 'pl'])]:
            self.assertEqual(parse_languages(value), (codes, False))
            self.assertEqual(parse_languages('/' + value), (codes, True))

    def test_invalid(self):
        for value in ('', '/', 'en/', 'en/en', 'en/unknown', 'en//uk'):
            with self.assertRaises(ValueError):
                parse_languages(value)
