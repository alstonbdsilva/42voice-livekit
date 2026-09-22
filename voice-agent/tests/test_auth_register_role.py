"""
Regression tests for P0-1: public registration must never create privileged roles.

- Public registration always creates CLIENT.
- role_name=ADMIN cannot escalate.
- role_name=SUPER_ADMIN cannot escalate.
- Normal registration still works and returns role_name CLIENT.
"""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock


class TestPublicRegistrationRoleEscalation(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        from api.modules.auth.services import AuthService
        self.service = AuthService()
        # Fully mock out repositories and token service.
        self.service.user_repository = MagicMock()
        self.service.token_repository = MagicMock()
        self.service.audit_repository = MagicMock()
        self.service.token_service = MagicMock()
        self.service.user_repository.find_by_email = AsyncMock(return_value=None)
        self.service.token_service.generate_opaque_token = MagicMock(return_value="opaque-token")
        self.service.token_service.save_verification_token = AsyncMock()
        self.service.audit_repository.create = AsyncMock()
        self.mock_settings = MagicMock()
        self.mock_settings.bcrypt_salt_rounds = 4
        self.mock_settings.backend_url = "http://localhost:8000/api/v1"

        self.idx = 0
        self.get_settings_patcher = patch("api.modules.auth.services.get_settings", return_value=self.mock_settings)
        self.get_settings_patcher.start()
        self.addCleanup(self.get_settings_patcher.stop)

    def _make_user_row(self, email: str, role_id: int) -> dict:
        self.idx += 1
        return {
            "id": f"00000000-0000-4000-8000-0000000000{self.idx:02d}",
            "email": email,
            "password_hash": "hashed",
            "first_name": "Test",
            "last_name": "User",
            "phone": None,
            "avatar_url": None,
            "role_id": role_id,
            "reseller_id": None,
            "client_id": None,
            "is_active": True,
            "is_verified": False,
        }

    async def _register(self, email: str, role_name: str) -> dict:
        """Call AuthService.register with a client-requested role_name."""
        dto = {
            "email": email,
            "password_hash": "Password123!",
            "first_name": "Test",
            "last_name": "User",
            "phone": None,
            "avatar_url": None,
            "role_name": role_name,
        }
        return await self.service.register(dto, "127.0.0.1", "unittest")

    async def test_normal_registration_creates_client_role(self):
        """Normal registration resolves the CLIENT role and returns it."""
        self.service.user_repository.get_role_id_by_name = AsyncMock(return_value=4)
        self.service.user_repository.create = AsyncMock(return_value=self._make_user_row("a@example.com", 4))

        result = await self._register("a@example.com", "CLIENT")

        self.assertEqual(result["role_name"], "CLIENT")
        # Role lookup must have been for CLIENT and the created user must use its id.
        self.service.user_repository.get_role_id_by_name.assert_called_once_with("CLIENT")
        created_dto = self.service.user_repository.create.await_args.args[0]
        self.assertEqual(created_dto["role_id"], 4)

    async def test_admin_role_cannot_escalate(self):
        """Client-supplied role_name=ADMIN must be ignored and forced to CLIENT."""
        self.service.user_repository.get_role_id_by_name = AsyncMock(return_value=4)
        self.service.user_repository.create = AsyncMock(return_value=self._make_user_row("b@example.com", 4))

        result = await self._register("b@example.com", "ADMIN")

        self.assertEqual(result["role_name"], "CLIENT")
        self.service.user_repository.get_role_id_by_name.assert_called_once_with("CLIENT")
        created_dto = self.service.user_repository.create.await_args.args[0]
        self.assertEqual(created_dto["role_id"], 4)

    async def test_super_admin_role_cannot_escalate(self):
        """Client-supplied role_name=SUPER_ADMIN must be ignored and forced to CLIENT."""
        self.service.user_repository.get_role_id_by_name = AsyncMock(return_value=4)
        self.service.user_repository.create = AsyncMock(return_value=self._make_user_row("c@example.com", 4))

        result = await self._register("c@example.com", "SUPER_ADMIN")

        self.assertEqual(result["role_name"], "CLIENT")
        self.service.user_repository.get_role_id_by_name.assert_called_once_with("CLIENT")
        created_dto = self.service.user_repository.create.await_args.args[0]
        self.assertEqual(created_dto["role_id"], 4)

    def test_register_request_model_has_no_role_field(self):
        """The public RegisterRequest model no longer exposes role_name."""
        from api.modules.auth.routes import RegisterRequest
        self.assertNotIn("role_name", RegisterRequest.model_fields)

    def test_register_request_ignores_extra_role_name_payload(self):
        """A body carrying role_name=SUPER_ADMIN is validated with CLIENT role only."""
        from api.modules.auth.routes import RegisterRequest
        req = RegisterRequest(
            email="d@example.com",
            password="Password123!",
            first_name="Test",
            last_name="User",
            role_name="SUPER_ADMIN",
        )
        model_dump = req.model_dump()
        self.assertNotIn("role_name", model_dump)


if __name__ == "__main__":
    unittest.main()