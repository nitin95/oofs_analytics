"""Load and maintain the encrypted driver blacklist used by generated pages."""

import argparse
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_ENCRYPTED_PATH = ROOT_DIR / 'assets' / 'driver_blacklist.enc'
DEFAULT_PLAINTEXT_PATH = ROOT_DIR / 'assets' / 'driver_blacklist.json'
KEY_ENV_VAR = 'OOFS_DRIVER_BLACKLIST_KEY'


def _read_key():
    key = os.environ.get(KEY_ENV_VAR)
    if not key:
        raise RuntimeError(f'{KEY_ENV_VAR} is required to load the driver blacklist')
    try:
        return key.encode('ascii')
    except UnicodeEncodeError as error:
        raise RuntimeError(f'{KEY_ENV_VAR} must be a Fernet key') from error


def _validate_payload(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get('drivers'), list):
        print(payload)
        raise ValueError('Blacklist JSON must contain a drivers list')

    return payload['drivers']


def _read_entries(encrypted_path, key):
    try:
        encrypted = Path(encrypted_path).read_bytes()
        payload = json.loads(Fernet(key).decrypt(encrypted))
        return _validate_payload(payload)
    except (InvalidToken, OSError, UnicodeError, ValueError) as error:
        raise RuntimeError(
            'Unable to decrypt or validate the driver blacklist; check its file and key'
        ) from error


def load_blacklisted_names(normalize_name, encrypted_path=DEFAULT_ENCRYPTED_PATH):
    """Return canonical blacklisted names, failing closed on missing/invalid data."""
    entries = _read_entries(encrypted_path, _read_key())
    return {normalize_name(entry) for entry in entries}


def encrypt_blacklist(plaintext_path=DEFAULT_PLAINTEXT_PATH,
                      encrypted_path=DEFAULT_ENCRYPTED_PATH):
    """Encrypt and validate a local JSON blacklist using the configured key."""
    try:
        payload = json.loads(Path(plaintext_path).read_text(encoding='utf-8'))
        _validate_payload(payload)
        encrypted = Fernet(_read_key()).encrypt(
            json.dumps(payload, ensure_ascii=True, indent=2).encode('utf-8')
        )
    except (OSError, UnicodeError, ValueError) as error:
        print(error)
        raise RuntimeError('Unable to read or validate the plaintext blacklist') from error

    output_path = Path(encrypted_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(encrypted)
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument('--generate-key', action='store_true')
    actions.add_argument('--encrypt', action='store_true')
    parser.add_argument('--input', type=Path, default=DEFAULT_PLAINTEXT_PATH)
    parser.add_argument('--output', type=Path, default=DEFAULT_ENCRYPTED_PATH)
    arguments = parser.parse_args()

    if arguments.generate_key:
        print(Fernet.generate_key().decode('ascii'))
        return

    output_path = encrypt_blacklist(arguments.input, arguments.output)
    print(f'Encrypted driver blacklist written to {output_path}')


if __name__ == '__main__':
    main()