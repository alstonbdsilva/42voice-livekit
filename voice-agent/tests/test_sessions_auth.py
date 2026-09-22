"""
Regression tests for P0-3: all sessions routes must require authentication.

- Every route on the sessions router is protected by get_current_user.
- An unauthenticated request is rejected with UnauthorizedError/TOKEN_MISSING.
- A valid authenticated user passes the dependency.
"""

import inspect
import unittest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.params import Depends
from starlette.requests import Request

from api.modules.sessions import routes as sessions_routes
from api.utils.errors import UnauthorizedError


class TestSessionsRoutesProtected(unittest.TestCase):

    def test_every_session_route_requires_authentication(self):
        """Each route handler declares current_user = Depends(get_current_user)."""
        unprotected = []
        for route in sessions_routes.router.routes:
            endpoint = getattr(route, "endpoint", None)
            if endpoint is None:
                continue
            params = inspect.signature(endpoint).parameters
            if "current_user" not in params or not isinstance(params["current_user"].default, Depends):
                unprotected.append((route.path, getattr(route, "methods", None)))
        self.assertEqual(unprotected, [], f"Routes missing authentication: {unprotected}")


class TestCurrentUserRejection(unittest.IsolatedAsyncioTestCase):

    def _request(self, headers=None):
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": headers or [],
            }
        )

    @patch("api.middlewares.auth.get_settings")
    async def test_missing_token_is_rejected(self, mock_get_settings):
        """Anonymous requests are rejected with UnauthorizedError."""
        mock_get_settings.return_value = MagicMock(jwt_access_secret="testsecret")
        from api.middlewares.auth import get_current_user
        req = self._request(headers=[])
        with self.assertRaises(UnauthorizedError):
            await get_current_user(req)

    @patch("api.middlewares.auth.database.query")
    @patch("api.middlewares.auth.get_settings")
    async def test_valid_token_is_accepted(self, mock_get_settings, mock_query):
        """A valid Bearer token for an active user passes the dependency."""
        mock_get_settings.return_value = MagicMock(jwt_access_secret="testsecret")
        import jwt
        token = jwt.encode({"id": "user-1", "email": "u@example.com"}, "testsecret", algorithm="HS256")
        mock_query.return_value = [
            {
                "id": "user-1",
                "email": "u@example.com",
                "is_active": True,
                "is_verified": True,
                "client_id": None,
                "reseller_id": None,
                "role": "CLIENT",
            }
        ]
        from api.middlewares.auth import get_current_user
        req = self._request(headers=[(b"authorization", f"Bearer {token}".encode())])
        user = await get_current_user(req)
        self.assertEqual(user["id"], "user-1")
        self.assertEqual(user["role"], "CLIENT")


if __name__ == "__main__":
    unittest.main()