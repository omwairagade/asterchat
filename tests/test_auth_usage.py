import base64
import json
import os
import unittest
from datetime import date
from unittest.mock import patch

import jwt
from fastapi import HTTPException

from aster import auth, db
from app_server import public_callback_origin, reset_time, validate_messages


class AuthAndUsageTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(
            os.environ,
            {
                "MANUS_PROJECT_ID": "aster-test",
                "MANUS_JWT_SECRET": "test-session-secret-that-is-at-least-32-bytes-long",
            },
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_oauth_state_round_trip_and_callback_path_validation(self):
        redirect = "https://asterchat.example/api/auth/callback"
        nonce, state = auth.create_oauth_state(redirect)
        parsed = auth.parse_oauth_state(state)
        self.assertEqual(parsed, {"redirectUri": redirect, "nonce": nonce})
        hostile_payload = base64.urlsafe_b64encode(
            json.dumps({"redirectUri": "https://evil.example/", "nonce": nonce}).encode()
        ).decode().rstrip("=")
        self.assertIsNone(auth.parse_oauth_state(hostile_payload))

    def test_session_is_project_scoped_and_expiring(self):
        token = auth.issue_session("manus-open-id")
        self.assertEqual(auth.session_open_id(token), "manus-open-id")
        other_project = jwt.encode(
            {"appId": "another-project", "openId": "manus-open-id", "exp": 4102444800},
            os.environ["MANUS_JWT_SECRET"],
            algorithm="HS256",
        )
        self.assertIsNone(auth.session_open_id(other_project))

    def test_origin_validation_rejects_paths_credentials_and_non_web_schemes(self):
        self.assertEqual(auth.validate_origin("https://asterchat.example"), "https://asterchat.example")
        for value in ["javascript:alert(1)", "https://user:pass@example.com", "https://example.com/path"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                auth.validate_origin(value)

    def test_callback_origin_is_limited_to_project_hosts_or_local_loopback(self):
        preview = "https://8328-im6byf23rn4o8zixely20-ce0d2e45.sg2.manus.computer"
        public = "https://asterchat-wfynpmap.manus.space"
        self.assertEqual(public_callback_origin(preview), preview)
        self.assertEqual(public_callback_origin(public), public)
        self.assertEqual(public_callback_origin("http://localhost:3000"), "http://localhost:3000")
        with self.assertRaises(HTTPException):
            public_callback_origin("https://attacker.example")

    def test_daily_reset_is_next_utc_midnight(self):
        self.assertEqual(reset_time(date(2026, 10, 2)), "2026-10-03T00:00:00Z")

    def test_account_key_is_stable_and_does_not_store_the_provider_identity(self):
        first = db.account_key("opaque-manus-identity")
        self.assertEqual(first, db.account_key("opaque-manus-identity"))
        self.assertNotEqual(first, "opaque-manus-identity")
        self.assertEqual(len(first), 64)

    def test_messages_must_be_bounded_and_end_with_user_prompt(self):
        messages = validate_messages([{"role": "user", "content": "Help me plan"}])
        self.assertEqual(messages[0]["role"], "user")
        with self.assertRaises(HTTPException):
            validate_messages([{"role": "assistant", "content": "Not a user turn"}])
        with self.assertRaises(HTTPException):
            validate_messages([{"role": "user", "content": "x" * 4001}])


if __name__ == "__main__":
    unittest.main()
