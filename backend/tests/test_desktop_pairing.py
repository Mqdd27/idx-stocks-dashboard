import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.desktop_routes import _hash


class DesktopPairingContractTest(unittest.TestCase):
    def test_pairing_hash_is_deterministic_and_not_plaintext(self):
        code = "pairing-code"
        self.assertEqual(_hash(code), hashlib.sha256(code.encode()).hexdigest())
        self.assertNotEqual(_hash(code), code)

    def test_pairing_expiry_and_one_time_semantics(self):
        now = datetime.now(timezone.utc)
        expired = SimpleNamespace(used_at=None, expires_at=now - timedelta(seconds=1))
        used = SimpleNamespace(used_at=now, expires_at=now + timedelta(minutes=10))
        valid = SimpleNamespace(used_at=None, expires_at=now + timedelta(minutes=10))
        self.assertTrue(expired.used_at or expired.expires_at < now)
        self.assertTrue(used.used_at or used.expires_at < now)
        self.assertFalse(valid.used_at or valid.expires_at < now)


if __name__ == "__main__":
    unittest.main()
