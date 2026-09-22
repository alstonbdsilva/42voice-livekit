"""
Regression tests for P1-6: database TLS must verify certificates in production.

- Production auto mode uses TLS with full certificate verification.
- Local development auto mode keeps no TLS (local PG compatibility).
- disable disables TLS even in production.
- require (explicit) enables encryption without verification.
- Never disables verification on the production auto path.
"""

import ssl
import unittest
from unittest.mock import MagicMock

from api.database import build_ssl_context


def _settings(environment="development", db_ssl_mode="auto", pghost="localhost"):
    s = MagicMock()
    s.environment = environment
    s.db_ssl_mode = db_ssl_mode
    s.pghost = pghost
    return s


class TestBuildSslContext(unittest.TestCase):

    def test_dev_auto_returns_none(self):
        """Local development keeps no TLS by default."""
        self.assertIsNone(build_ssl_context(_settings(environment="development", db_ssl_mode="auto")))

    def test_production_auto_verifies_certificates(self):
        """Production auto must verify certificates (no CERT_NONE)."""
        ctx = build_ssl_context(_settings(environment="production", db_ssl_mode="auto"))
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)

    def test_supabase_host_in_dev_verifies_certificates(self):
        """A supabase.co host triggers full verification even if dev flags are set."""
        ctx = build_ssl_context(_settings(environment="development", db_ssl_mode="auto", pghost="db.supabase.co"))
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(ctx.check_hostname)

    def test_disable_mode_returns_none_in_production(self):
        """Explicit disable keeps TLS off even in production."""
        self.assertIsNone(build_ssl_context(_settings(environment="production", db_ssl_mode="disable")))

    def test_require_mode_enables_encryption_without_verification(self):
        """Explicit require mode allows encryption with CERT_NONE (operator opt-in only)."""
        ctx = build_ssl_context(_settings(environment="production", db_ssl_mode="require"))
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)
        self.assertFalse(ctx.check_hostname)

    def test_unsupported_mode_raises(self):
        """Invalid DB_SSL_MODE values fail fast."""
        with self.assertRaises(ValueError):
            build_ssl_context(_settings(environment="production", db_ssl_mode="bogus"))


if __name__ == "__main__":
    unittest.main()