import json
import os
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

import driver_blacklist


class DriverBlacklistTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.encrypted_path = os.path.join(self.temp_dir.name, 'blacklist.enc')
        self.key = Fernet.generate_key()

    def tearDown(self):
        self.temp_dir.cleanup()

    def encrypt_payload(self, payload, key=None):
        selected_key = key or self.key
        encrypted = Fernet(selected_key).encrypt(json.dumps(payload).encode('utf-8'))
        with open(self.encrypted_path, 'wb') as encrypted_file:
            encrypted_file.write(encrypted)

    def test_load_normalizes_names_and_keeps_reason_private(self):
        self.encrypt_payload({
            'drivers': [{'name': 'Greg Kach', 'reason': 'Private administrative note'}],
        })

        with patch.dict(os.environ, {
            driver_blacklist.KEY_ENV_VAR: self.key.decode('ascii'),
        }):
            names = driver_blacklist.load_blacklisted_names(
                lambda name: name.strip().casefold(), self.encrypted_path
            )

        self.assertEqual(names, {'greg kach'})
        self.assertNotIn('Private administrative note', repr(names))

    def test_empty_blacklist_is_valid(self):
        self.encrypt_payload({'drivers': []})

        with patch.dict(os.environ, {
            driver_blacklist.KEY_ENV_VAR: self.key.decode('ascii'),
        }):
            names = driver_blacklist.load_blacklisted_names(str, self.encrypted_path)

        self.assertEqual(names, set())

    def test_missing_key_fails_closed(self):
        self.encrypt_payload({'drivers': []})

        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'is required'):
                driver_blacklist.load_blacklisted_names(str, self.encrypted_path)

    def test_invalid_key_or_payload_fails_closed(self):
        self.encrypt_payload({'drivers': []})

        with patch.dict(os.environ, {
            driver_blacklist.KEY_ENV_VAR: Fernet.generate_key().decode('ascii'),
        }):
            with self.assertRaisesRegex(RuntimeError, 'Unable to decrypt'):
                driver_blacklist.load_blacklisted_names(str, self.encrypted_path)

        self.encrypt_payload({'drivers': [{'name': 'No reason'}]})
        with patch.dict(os.environ, {
            driver_blacklist.KEY_ENV_VAR: self.key.decode('ascii'),
        }):
            with self.assertRaisesRegex(RuntimeError, 'Unable to decrypt'):
                driver_blacklist.load_blacklisted_names(str, self.encrypted_path)


if __name__ == '__main__':
    unittest.main()