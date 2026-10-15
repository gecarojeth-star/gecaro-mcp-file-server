import asyncio
import unittest

from server import config
from server.auth import MIN_TOKEN_LENGTH, TokenAuthMiddleware, check_startup_auth

TOKEN = "t" * 32


async def _inner_app(scope, receive, send):
    if scope["type"] == "lifespan":
        scope["seen"] = True
        return
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": scope["path"].encode()})


def call(path, headers=None, token=TOKEN):
    app = TokenAuthMiddleware(_inner_app, token)
    sent = []

    async def send(msg):
        sent.append(msg)

    async def receive():
        return {"type": "http.request"}

    scope = {"type": "http", "path": path, "raw_path": path.encode(),
             "headers": [(k.encode(), v.encode()) for k, v in (headers or {}).items()]}
    asyncio.run(app(scope, receive, send))
    status = sent[0]["status"]
    body = sent[1]["body"].decode()
    return status, body


class AuthTests(unittest.TestCase):
    def test_no_credentials_is_401(self):
        self.assertEqual(call("/mcp")[0], 401)

    def test_wrong_bearer_is_401(self):
        self.assertEqual(call("/mcp", {"Authorization": "Bearer nope"})[0], 401)
        self.assertEqual(call("/mcp", {"Authorization": "Basic " + TOKEN})[0], 401)
        self.assertEqual(call("/mcp", {"Authorization": TOKEN})[0], 401)

    def test_correct_bearer_passes_and_path_unchanged(self):
        self.assertEqual(call("/mcp", {"Authorization": f"Bearer {TOKEN}"}), (200, "/mcp"))
        self.assertEqual(call("/mcp", {"authorization": f"bearer {TOKEN}"})[0], 200)

    def test_secret_path_passes_and_prefix_is_stripped(self):
        self.assertEqual(call(f"/{TOKEN}/mcp"), (200, "/mcp"))

    def test_wrong_or_partial_secret_path_is_401(self):
        self.assertEqual(call("/wrong/mcp")[0], 401)
        self.assertEqual(call(f"/{TOKEN[:-1]}/mcp")[0], 401)
        self.assertEqual(call(f"/{TOKEN}x/mcp")[0], 401)

    def test_401_body_does_not_leak_token(self):
        self.assertNotIn(TOKEN, call("/mcp")[1])

    def test_lifespan_is_not_blocked(self):
        app = TokenAuthMiddleware(_inner_app, TOKEN)
        scope = {"type": "lifespan"}
        asyncio.run(app(scope, None, None))
        self.assertTrue(scope.get("seen"))

    def test_empty_token_is_rejected(self):
        with self.assertRaises(ValueError):
            TokenAuthMiddleware(_inner_app, "")


class StartupGuardTests(unittest.TestCase):
    def setUp(self):
        self._old = (config.AUTH_TOKEN, config.HOST)

    def tearDown(self):
        config.AUTH_TOKEN, config.HOST = self._old

    def test_short_token_refused(self):
        config.AUTH_TOKEN, config.HOST = "short", "127.0.0.1"
        with self.assertRaises(SystemExit):
            check_startup_auth()

    def test_no_token_on_public_host_refused(self):
        config.AUTH_TOKEN, config.HOST = "", "0.0.0.0"
        with self.assertRaises(SystemExit):
            check_startup_auth()

    def test_no_token_on_localhost_allowed(self):
        config.AUTH_TOKEN, config.HOST = "", "127.0.0.1"
        check_startup_auth()

    def test_good_token_allowed(self):
        config.AUTH_TOKEN, config.HOST = "x" * MIN_TOKEN_LENGTH, "0.0.0.0"
        check_startup_auth()


if __name__ == "__main__":
    unittest.main()
