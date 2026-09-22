"""
Regression tests for P0-2: init_db must never reset admin credentials.

- Existing users are never overwritten (ON CONFLICT (email) DO NOTHING).
- No hardcoded/default admin passwords remain in source control.
- Seed users are only created when their SEED_*_PASSWORD env var is set.
- Stored password is bcrypt-hashed, never the plaintext value.
"""

import unittest
import pathlib
from unittest.mock import patch, AsyncMock, MagicMock

import bcrypt

INIT_DB_PATH = pathlib.Path(__file__).resolve().parent.parent / "api" / "init_db.py"


class TestInitDbSeeding(unittest.TestCase):

    def test_source_seed_insert_never_overwrites(self):
        """The bootstrap user INSERT uses ON CONFLICT DO NOTHING, not DO UPDATE."""
        src = INIT_DB_PATH.read_text(encoding="utf-8")
        seed_block = src[src.index("seed_default_users"):]
        self.assertIn("ON CONFLICT (email) DO NOTHING", seed_block)
        self.assertNotIn("DO UPDATE", seed_block)

    def test_source_has_no_hardcoded_seed_passwords(self):
        """No default admin passwords are stored in source control."""
        src = INIT_DB_PATH.read_text(encoding="utf-8")
        for banned in ["Admin@42voice", "Finance@42voice", "Reseller@42voice", "Client@42voice"]:
            self.assertNotIn(banned, src)
        # DEFAULT_SEED_USERS must reference env vars, not literal passwords.
        self.assertIn("password_env", src)
        self.assertIn("SEED_SUPER_ADMIN_PASSWORD", src)

    def test_seed_uses_env_var_names_for_every_account(self):
        """Every bootstrap account maps to a SEED_*_PASSWORD env var."""
        from api.init_db import DEFAULT_SEED_USERS
        self.assertEqual(len(DEFAULT_SEED_USERS), 4)
        self.assertTrue(all("password_env" in u and "password" not in u for u in DEFAULT_SEED_USERS))
        self.assertTrue(all(u["password_env"].startswith("SEED_") for u in DEFAULT_SEED_USERS))


class TestSeedDefaultUsersRuntime(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        import api.init_db as init_db
        self.init_db = init_db
        self.pool_patcher = patch("api.init_db.database.query", new=AsyncMock())
        self.mock_query = self.pool_patcher.start()
        self.addCleanup(self.pool_patcher.stop)
        self.roles_map = {
            "SUPER_ADMIN": 1,
            "FINANCE_ADMIN": 2,
            "RESELLER": 3,
            "CLIENT": 4,
        }

    async def test_missing_env_password_skips_insert(self):
        """No env password -> the account is skipped entirely."""
        env = {"SEED_CLIENT_PASSWORD": "ClientPass123"}
        await self.init_db.seed_default_users(self.roles_map, 4, env_getter=env.get)
        # Only the CLIENT account may attempt an insert.
        self.mock_query.assert_awaited_once()
        args = self.mock_query.await_args.args
        sql, params = args[0], args[1]
        self.assertEqual(params[0], "client@42voice.com")

    async def test_short_env_password_is_skipped(self):
        """Passwords shorter than the policy are rejected, nothing inserted."""
        env = {"SEED_SUPER_ADMIN_PASSWORD": "short"}
        await self.init_db.seed_default_users(self.roles_map, 4, env_getter=env.get)
        self.mock_query.assert_not_awaited()

    async def test_seed_stores_bcrypt_hash_not_plaintext(self):
        """Seeding stores a bcrypt hash and verifiable plaintext check succeeds."""
        env = {"SEED_CLIENT_PASSWORD": "ClientPass123"}
        await self.init_db.seed_default_users(self.roles_map, 4, env_getter=env.get)
        self.mock_query.assert_awaited_once()
        args = self.mock_query.await_args.args
        sql, params = args[0], args[1]
        self.assertNotIn("ClientPass123", repr(params[1]))
        self.assertTrue(bcrypt.checkpw(b"ClientPass123", params[1].encode("utf-8")), "stored password must hash-match plaintext")
        self.assertNotEqual(params[1], "ClientPass123")

    async def test_insert_sql_uses_do_nothing(self):
        """The emitted INSERT has ON CONFLICT (email) DO NOTHING semantics."""
        env = {"SEED_CLIENT_PASSWORD": "ClientPass123"}
        await self.init_db.seed_default_users(self.roles_map, 4, env_getter=env.get)
        sql = self.mock_query.await_args.args[0]
        self.assertIn("ON CONFLICT (email) DO NOTHING", sql)
        self.assertNotIn("DO UPDATE", sql)


if __name__ == "__main__":
    unittest.main()