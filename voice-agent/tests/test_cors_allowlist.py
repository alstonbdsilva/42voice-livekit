"""
Regression tests for P1-5: CORS must use a controlled allowlist, not a wildcard.

- Allowed origins derive from configured FRONTEND_URL / BACKEND_URL.
- Unrelated external origins are rejected on OPTIONS preflight.
- A configured origin works on OPTIONS preflight.
- No wildcard origin regex remains.
"""

import unittest
from unittest.mock import patch, MagicMock
import httpx

from main import app, build_cors_origins


class TestBuildCorsOrigins(unittest.TestCase):

    @patch("main.get_settings")
    def test_origins_derived_from_configured_urls(self, mock_get_settings):
        mock_get_settings.return_value = MagicMock(
            frontend_url="https://app.example.com",
            backend_url="http://api.example.com/api/v1",
        )
        origins = build_cors_origins()
        self.assertIn("https://app.example.com", origins)
        self.assertIn("http://api.example.com", origins)
        # Paths must be stripped; only scheme://netloc remains.
        self.assertNotIn("/api/v1", "".join(origins))

    @patch("main.get_settings")
    def test_no_wildcard_and_no_duplicates(self, mock_get_settings):
        mock_get_settings.return_value = MagicMock(
            frontend_url="https://app.example.com",
            backend_url="https://app.example.com",
        )
        origins = build_cors_origins()
        self.assertEqual(origins, ["https://app.example.com"])
        self.assertTrue(all("*" not in o for o in origins))

    def test_app_uses_no_allow_origin_regex(self):
        """The application's CORS middleware must not use the wildcard regex."""
        cors_middleware = None
        for mw in app.user_middleware:
            if getattr(mw, "cls", None).__name__ == "CORSMiddleware":
                cors_middleware = mw
                break
        self.assertIsNotNone(cors_middleware, "CORSMiddleware not configured")
        kwargs = cors_middleware.kwargs
        self.assertNotIn("allow_origin_regex", kwargs)
        self.assertTrue(kwargs.get("allow_origins"))
        self.assertTrue(all("*" not in o for o in kwargs["allow_origins"]))


class TestCorsPreflight(unittest.IsolatedAsyncioTestCase):

    async def _preflight(self, origin: str):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.options(
                "/api/v1/health",
                headers={
                    "origin": origin,
                    "access-control-request-method": "GET",
                    "access-control-request-headers": "authorization,content-type",
                },
            )

    async def test_configured_origin_allowed_on_preflight(self):
        configured = build_cors_origins()
        if not configured:
            self.skipTest("No configured CORS origin available")
        resp = await self._preflight(configured[0])
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get("access-control-allow-origin"), configured[0])

    async def test_unrelated_external_origin_rejected(self):
        resp = await self._preflight("https://evil.example.com")
        self.assertNotIn("access-control-allow-origin", resp.headers)


if __name__ == "__main__":
    unittest.main()