from __future__ import annotations

import unittest

from pokecrack_browser.redaction import REDACTED, redact, redact_text, strip_ansi


class RedactionTests(unittest.TestCase):
    def test_recursive_secrets_and_cookie_headers_are_redacted(self) -> None:
        value = {
            "title": "safe",
            "token": "super-secret-token",
            "nested": {
                "Authorization": "Bearer abc.def.ghi",
                "set-cookie": "session=very-secret; HttpOnly",
                "safe": "Cookie: sid=hidden\nAuthorization: Bearer hidden-token",
            },
            "items": [{"api_key": "key-value"}],
        }

        redacted = redact(value)

        self.assertEqual(redacted["token"], REDACTED)
        self.assertEqual(redacted["nested"]["Authorization"], REDACTED)
        self.assertEqual(redacted["nested"]["set-cookie"], REDACTED)
        self.assertEqual(redacted["items"][0]["api_key"], REDACTED)
        serialized = str(redacted)
        for secret in (
            "super-secret-token",
            "abc.def.ghi",
            "very-secret",
            "hidden-token",
            "key-value",
        ):
            self.assertNotIn(secret, serialized)

    def test_structured_redaction_catches_camel_case_session_keys(self) -> None:
        raw = {"metadata": {"sessionData": "SESSION-SECRET", "sessionID": "ID-SECRET"}}

        cleaned = redact(raw)

        self.assertEqual(cleaned["metadata"]["sessionData"], REDACTED)
        self.assertEqual(cleaned["metadata"]["sessionID"], REDACTED)
        self.assertEqual(raw["metadata"]["sessionData"], "SESSION-SECRET")

    def test_session_identifier_mapping_keys_are_redacted(self) -> None:
        value = {
            "metadata": {
                "session_id": "SESSION-CREDENTIAL",
                "sid": "SID-CREDENTIAL",
                "auth": "AUTH-CREDENTIAL",
                "author": "safe-name",
            }
        }

        redacted = redact(value)

        self.assertEqual(redacted["metadata"]["session_id"], REDACTED)
        self.assertEqual(redacted["metadata"]["sid"], REDACTED)
        self.assertEqual(redacted["metadata"]["auth"], REDACTED)
        self.assertEqual(redacted["metadata"]["author"], "safe-name")

    def test_session_identifier_assignments_are_redacted_from_text(self) -> None:
        raw = (
            "session_id=SESSION-CREDENTIAL sid:SID-CREDENTIAL auth=AUTH-CREDENTIAL author=safe-name"
        )

        cleaned = redact_text(raw)

        self.assertNotIn("SESSION-CREDENTIAL", cleaned)
        self.assertNotIn("SID-CREDENTIAL", cleaned)
        self.assertNotIn("AUTH-CREDENTIAL", cleaned)
        self.assertIn("author=safe-name", cleaned)

    def test_quoted_json_session_credentials_are_redacted_from_text(self) -> None:
        raw = (
            '{"session_id":"SESSION-CREDENTIAL","sid":"SID-CREDENTIAL",'
            '"auth":"AUTH-CREDENTIAL","author":"safe-name"}'
        )

        cleaned = redact_text(raw)

        self.assertNotIn("SESSION-CREDENTIAL", cleaned)
        self.assertNotIn("SID-CREDENTIAL", cleaned)
        self.assertNotIn("AUTH-CREDENTIAL", cleaned)
        self.assertIn('"author":"safe-name"', cleaned)
        self.assertEqual(cleaned.count(REDACTED), 3)

    def test_camel_case_session_data_is_redacted_from_captured_text(self) -> None:
        raw = '{"sessionData":"SESSION-DATA-CREDENTIAL"} sessionData=ASSIGNMENT-CREDENTIAL'

        cleaned = redact_text(raw)

        self.assertNotIn("SESSION-DATA-CREDENTIAL", cleaned)
        self.assertNotIn("ASSIGNMENT-CREDENTIAL", cleaned)
        self.assertEqual(cleaned.count(REDACTED), 2)

    def test_text_redaction_handles_headers_and_url_credentials(self) -> None:
        raw = (
            "Authorization: Bearer abc123\n"
            "Cookie: session=secret-value\n"
            "https://user:pass@example.invalid/path?access_token=qwerty&safe=1#private"
        )
        cleaned = redact_text(raw)
        self.assertNotIn("abc123", cleaned)
        self.assertNotIn("secret-value", cleaned)
        self.assertNotIn("qwerty", cleaned)
        self.assertNotIn("user:pass", cleaned)
        self.assertNotIn("?", cleaned)
        self.assertNotIn("#private", cleaned)
        self.assertIn("https://example.invalid/path", cleaned)
        self.assertIn(REDACTED, cleaned)

    def test_ansi_sequences_are_removed_before_json_or_diagnostics(self) -> None:
        self.assertEqual(strip_ansi("\x1b[31merror\x1b[0m"), "error")


if __name__ == "__main__":
    unittest.main()
