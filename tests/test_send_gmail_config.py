import tempfile
import unittest
from pathlib import Path
from unittest import mock

import send_gmail
import service_config


class SendGmailConfigTests(unittest.TestCase):
    def test_load_config_prefers_project_env_local(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            project_env = tmp_path / ".env.local"
            legacy_env = tmp_path / "legacy.env"
            project_env.write_text(
                "GMAIL_ADDRESS=project@example.com\n"
                "GMAIL_APP_PASSWORD=project-password\n",
                encoding="utf-8",
            )
            legacy_env.write_text(
                "GMAIL_ADDRESS=legacy@example.com\n"
                "GMAIL_APP_PASSWORD=legacy-password\n",
                encoding="utf-8",
            )

            with mock.patch.object(service_config, "DEFAULT_ENV_FILE", project_env), mock.patch.object(
                service_config, "LEGACY_GMAIL_ENV_FILE", legacy_env
            ):
                config, error = send_gmail.load_config()

        self.assertIsNone(error)
        self.assertEqual(config["email"], "project@example.com")
        self.assertEqual(config["app_password"], "project-password")

    def test_load_config_reports_project_local_secret_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            project_env = tmp_path / ".env.local"
            legacy_env = tmp_path / "legacy.env"

            with mock.patch.object(service_config, "DEFAULT_ENV_FILE", project_env), mock.patch.object(
                service_config, "LEGACY_GMAIL_ENV_FILE", legacy_env
            ):
                config, error = send_gmail.load_config()

        self.assertIsNone(config)
        self.assertIn(".env.local", error)
        self.assertIn("GMAIL_ADDRESS", error)
        self.assertIn("GMAIL_APP_PASSWORD", error)


if __name__ == "__main__":
    unittest.main()
