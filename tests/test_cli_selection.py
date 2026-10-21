"""Offline regression coverage for the source review findings."""
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


from zotify.config import CONFIG_VALUES, Config, Zotify
from zotify.const import DEFAULT, TYPE, ROOT_PATH, ROOT_PODCAST_PATH, FETCH_DELAY, RETRY_ATTEMPTS, EXPORT_ZMD_LOCATION
from zotify.utils import safe_typecast  # pylint: disable=wrong-import-position

IMPORT_ROOT = tempfile.TemporaryDirectory(  # pylint: disable=consider-using-with
    prefix='zotify-review-import-'
)
Config.Values.update({key: safe_typecast(value, DEFAULT, value[TYPE])
                      for key, value in CONFIG_VALUES.items()})
Config.Values.update({ROOT_PATH: IMPORT_ROOT.name, ROOT_PODCAST_PATH: IMPORT_ROOT.name})

from zotify.__main__ import main  # pylint: disable=wrong-import-position,ungrouped-imports
from zotify.api import Content, UserItem  # pylint: disable=wrong-import-position


def tearDownModule():  # pylint: disable=invalid-name
    """Remove only this module's disposable import directory."""
    IMPORT_ROOT.cleanup()


class RegressionTests(unittest.TestCase):
    """Test actual code paths without credentials, accounts or real media."""

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(
            tempfile.TemporaryDirectory(prefix='zotify-review-test-')
        ))
        config = {key: safe_typecast(value, DEFAULT, value[TYPE])
                  for key, value in CONFIG_VALUES.items()}
        config.update({ROOT_PATH: str(self.root), ROOT_PODCAST_PATH: str(self.root),
                       FETCH_DELAY: 0.0, RETRY_ATTEMPTS: 0,
                       EXPORT_ZMD_LOCATION: str(self.root / 'cache')})
        self.enter_context(patch.object(Config, 'Values', config))
        self.enter_context(patch.object(Zotify, 'TOTAL_API_CALLS', 0))
        self.enter_context(patch.object(Content, 'ALL_NODES', {}))
        self.enter_context(patch('requests.sessions.Session.request',
                                side_effect=AssertionError('Network forbidden')))
        self.enter_context(patch('socket.create_connection',
                                side_effect=AssertionError('Network forbidden')))

    def enter_context(self, context):
        """Use cleanup-backed contexts on the supported Python 3.10 baseline."""
        return self.stack.enter_context(context)


    def test_all_menu_selection_keeps_first_and_only_choice(self):
        """Option zero means every response, including a singleton list."""
        choices = [{'name': 'First'}, {'name': 'Second'}]
        with patch('zotify.api.select', return_value=[None]), patch('zotify.api.Printer.table'):
            for items in (choices, choices[:1]):
                self.assertEqual(UserItem('review').display_select_user_items(items), items)

    def test_cli_accepts_both_m3u8_aliases(self):
        """Exercise the real CLI parser and stop before boot or login."""
        class StopBoot(Exception):
            """Stop immediately after parsing."""
        for flag in ('-e', '--export-m3u8'):
            with patch.object(sys, 'argv', ['zotify', flag, 'True']), \
                 patch.object(Zotify, 'boot', side_effect=StopBoot) as boot:
                with self.assertRaises(StopBoot):
                    main()
            self.assertEqual(boot.call_args.args[0].export_m3u8, 'True')


if __name__ == '__main__':
    unittest.main()
