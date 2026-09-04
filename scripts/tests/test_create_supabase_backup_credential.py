from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

from scripts import create_supabase_backup_credential as credential


PROJECT_REF = "a" * 20
TOKEN = "sbp_fixture_owner_token_123456"
POOLER = (
    f"postgresql://postgres.{PROJECT_REF}:[YOUR-PASSWORD]@"
    "aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"
)


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        return self.payload[:limit]


class _Opener:
    def __init__(self, payloads: list[object]) -> None:
        self.payloads = payloads
        self.requests: list[object] = []

    def open(self, request: object, *, timeout: float) -> _Response:
        self.requests.append((request, timeout))
        return _Response(self.payloads.pop(0))


class _API:
    def __init__(self) -> None:
        self.deleted = 0
        self.roles: list[str] = []

    def pooler_config(self) -> object:
        return [{"database_type": "PRIMARY", "connection_string": POOLER}]

    def create_login_role(self) -> object:
        self.roles = ["cli_login_postgres"]
        return {
            "role": "cli_login_postgres",
            "password": "fixture:/?#[]@ secret",
            "ttl_seconds": 3600,
        }

    def query(self, sql: str) -> object:
        self.last_query = sql
        return [{"role": role} for role in self.roles]

    def delete_login_roles(self) -> None:
        self.deleted += 1
        self.roles = []


class TemporaryBackupCredentialTests(unittest.TestCase):
    def test_management_requests_keep_token_out_of_payload_and_reject_redirects(self) -> None:
        opener = _Opener(
            [
                {"role": "cli_login_postgres", "password": "secret", "ttl_seconds": 3600},
                {"message": "ok"},
            ]
        )
        with patch.object(
            credential.urllib.request, "build_opener", return_value=opener
        ) as build_opener:
            api = credential.SupabaseManagementAPI(
                token=TOKEN, project_ref=PROJECT_REF
            )
            api.create_login_role()
            api.delete_login_roles()

        create_request, timeout = opener.requests[0]
        delete_request, _ = opener.requests[1]
        self.assertEqual(timeout, 60.0)
        self.assertEqual(
            create_request.full_url,
            f"https://api.supabase.com/v1/projects/{PROJECT_REF}/cli/login-role",
        )
        self.assertEqual(create_request.data, b'{"read_only":false}')
        self.assertNotIn(TOKEN.encode("utf-8"), create_request.data)
        self.assertEqual(create_request.get_header("Authorization"), f"Bearer {TOKEN}")
        self.assertEqual(delete_request.method, "DELETE")
        redirect_handler = build_opener.call_args.args[0]
        self.assertIsInstance(redirect_handler, credential._RejectRedirects)
        self.assertIsNone(
            redirect_handler.redirect_request(
                create_request,
                object(),
                302,
                "Found",
                {"Location": "https://evil.example.invalid/steal"},
                "https://evil.example.invalid/steal",
            )
        )

    def test_database_url_uses_session_pooler_and_connection_time_postgres_role(self) -> None:
        database_url = credential.build_database_url(
            pooler_connection=POOLER,
            project_ref=PROJECT_REF,
            role="cli_login_postgres",
            password="fixture:/?#[]@ secret",
        )
        self.assertIn("aws-0-ap-southeast-2.pooler.supabase.com:5432", database_url)
        self.assertIn(f"cli_login_postgres.{PROJECT_REF}", database_url)
        self.assertIn("fixture%3A%2F%3F%23%5B%5D%40%20secret", database_url)
        self.assertIn("sslmode=verify-full", database_url)
        self.assertIn("sslrootcert=system", database_url)
        self.assertIn("options=-c%20role%3Dpostgres", database_url)
        self.assertNotIn("[YOUR-PASSWORD]", database_url)

    def test_database_url_rejects_untrusted_or_ambiguous_pooler_shapes(self) -> None:
        invalid = (
            POOLER.replace("pooler.supabase.com", "evil.example.invalid"),
            POOLER.replace(f"postgres.{PROJECT_REF}", "postgres.wrongtenant"),
            POOLER.replace("/postgres", "/other"),
            POOLER + "?options=statement_timeout%3D0",
        )
        for pooler in invalid:
            with self.subTest(pooler=pooler), self.assertRaises(
                credential.TemporaryCredentialError
            ):
                credential.build_database_url(
                    pooler_connection=pooler,
                    project_ref=PROJECT_REF,
                    role="cli_login_postgres",
                    password="secret",
                )

    def test_create_writes_one_owner_only_line_without_printing_credentials(self) -> None:
        api = _API()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "database-url")
            role_output = Path(directory, "login-role")
            credential.create(
                api,
                project_ref=PROJECT_REF,
                output=output,
                role_output=role_output,
            )
            content = output.read_text(encoding="utf-8")
            self.assertEqual(len(content.splitlines()), 1)
            self.assertIn("cli_login_postgres", content)
            self.assertIn("fixture%3A", content)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            self.assertEqual(
                role_output.read_text(encoding="utf-8"), "cli_login_postgres\n"
            )
            self.assertEqual(stat.S_IMODE(role_output.stat().st_mode), 0o600)
            self.assertEqual(api.deleted, 0)

    def test_create_cleans_up_login_role_when_output_already_exists(self) -> None:
        api = _API()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "database-url")
            role_output = Path(directory, "login-role")
            output.write_text("protected\n", encoding="utf-8")
            with self.assertRaises(credential.TemporaryCredentialError):
                credential.create(
                    api,
                    project_ref=PROJECT_REF,
                    output=output,
                    role_output=role_output,
                )
            self.assertEqual(api.deleted, 1)
            self.assertEqual(output.read_text(encoding="utf-8"), "protected\n")

    def test_output_directory_must_be_owner_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory, "shared")
            parent.mkdir(mode=0o755)
            with self.assertRaises(credential.TemporaryCredentialError):
                credential._write_owner_only(parent / "database-url", "secret")
            self.assertFalse((parent / "database-url").exists())

    def test_login_shape_requires_a_long_enough_ttl(self) -> None:
        for payload in (
            {"role": "postgres", "password": "secret", "ttl_seconds": 3600},
            {"role": "cli_login_postgres", "password": "secret", "ttl_seconds": 299},
            {"role": "cli_login_postgres", "password": "secret", "ttl_seconds": 3601},
            {"role": "cli_login_postgres", "password": "bad\nsecret", "ttl_seconds": 3600},
        ):
            with self.subTest(payload=payload), self.assertRaises(
                credential.TemporaryCredentialError
            ):
                credential._login(payload)

    def test_create_cleans_up_after_a_malformed_success_response(self) -> None:
        api = _API()

        def malformed_login() -> object:
            api.roles = ["cli_login_postgres"]
            return {
                "role": "cli_login_postgres",
                "password": "secret",
                "ttl_seconds": 299,
            }

        api.create_login_role = malformed_login
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(credential.TemporaryCredentialError):
                credential.create(
                    api,
                    project_ref=PROJECT_REF,
                    output=Path(directory, "database-url"),
                    role_output=Path(directory, "login-role"),
                )
        self.assertEqual(api.deleted, 1)

    def test_create_reports_cleanup_failure_instead_of_masking_it(self) -> None:
        api = _API()

        def cleanup_failure() -> None:
            raise credential.TemporaryCredentialError("fixture cleanup failed")

        api.delete_login_roles = cleanup_failure
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory, "database-url")
            output.write_text("protected\n", encoding="utf-8")
            with self.assertRaisesRegex(
                credential.TemporaryCredentialError,
                "cleanup could not be confirmed",
            ):
                credential.create(
                    api,
                    project_ref=PROJECT_REF,
                    output=output,
                    role_output=Path(directory, "login-role"),
                )

    def test_create_refuses_to_replace_an_existing_cli_login(self) -> None:
        api = _API()
        api.roles = ["cli_login_other"]
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                credential.TemporaryCredentialError, "another CLI login"
            ):
                credential.create(
                    api,
                    project_ref=PROJECT_REF,
                    output=Path(directory, "database-url"),
                    role_output=Path(directory, "login-role"),
                )
        self.assertEqual(api.deleted, 0)

    def test_cleanup_deletes_only_the_exact_sole_login_and_verifies_absence(self) -> None:
        api = _API()
        api.roles = ["cli_login_postgres"]
        credential.delete_expected_login_role(
            api, expected_role="cli_login_postgres"
        )
        self.assertEqual(api.deleted, 1)
        self.assertEqual(api.roles, [])
        self.assertIn("left(rolname, 10) = 'cli_login_'", api.last_query)

    def test_cleanup_refuses_collective_delete_when_another_login_is_active(self) -> None:
        api = _API()
        api.roles = ["cli_login_other", "cli_login_postgres"]
        with self.assertRaisesRegex(
            credential.TemporaryCredentialError, "another CLI login"
        ):
            credential.delete_expected_login_role(
                api, expected_role="cli_login_postgres"
            )
        self.assertEqual(api.deleted, 0)

    def test_cli_project_ref_must_match_the_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                credential.PROJECT_ENV: PROJECT_REF,
                credential.TOKEN_ENV: TOKEN,
            },
            clear=True,
        ):
            arguments = credential.build_parser().parse_args(
                ["delete", "--project-ref", "b" * 20]
            )
            with self.assertRaises(credential.TemporaryCredentialError):
                credential.run(arguments)


if __name__ == "__main__":
    unittest.main()
