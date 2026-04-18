import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import service_config


class ServiceConfigTests(unittest.TestCase):
    def test_load_service_config_merges_files_and_env_overrides(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            config_path = tmp_path / "service.json"
            local_config_path = tmp_path / "service.local.json"
            repo_path = tmp_path / "asset_prices_repo"
            data_path = repo_path / "data"
            data_path.mkdir(parents=True)

            config_path.write_text(
                json.dumps(
                    {
                        "asset_prices": {
                            "repo_path": "/tmp/default-repo",
                            "data_dir": "/tmp/default-data",
                            "data_type": "adjusted",
                        },
                        "monitor": {
                            "symbol": "VOO",
                            "source": "alpaca",
                            "original_start": "2016-11-08",
                            "original_end": "2020-11-03",
                            "new_start": "2024-11-05",
                            "new_end": "today",
                            "sma_window": 100,
                            "plot_bands": True,
                            "plot_bollinger_bands": False,
                            "check_frequency_minutes": 15,
                        },
                        "alerts": {"enabled": True, "recipients": []},
                        "runtime": {
                            "html_output_path": "./plots/index.html",
                            "log_path": "./runtime/main.log",
                        },
                    }
                ),
                encoding="utf-8",
            )
            local_config_path.write_text(
                json.dumps(
                    {
                        "monitor": {"symbol": "SPY"},
                        "alerts": {"recipients": ["ops@example.com"]},
                    }
                ),
                encoding="utf-8",
            )

            config, metadata, error = service_config.load_service_config(
                config_path=config_path,
                local_config_path=local_config_path,
                env={
                    "ASSET_PRICES_REPO": str(repo_path),
                    "ASSET_PRICES_DATA_DIR": str(data_path),
                    "ASSET_PRICES_DATA_TYPE": "raw",
                },
            )

            self.assertIsNone(error)
            self.assertEqual(config["monitor"]["symbol"], "SPY")
            self.assertEqual(config["alerts"]["recipients"], ["ops@example.com"])
            self.assertEqual(config["asset_prices"]["repo_path"], str(repo_path))
            self.assertEqual(config["asset_prices"]["data_dir"], str(data_path))
            self.assertEqual(config["asset_prices"]["data_type"], "raw")
            self.assertEqual(config["monitor"]["new_end"], date.today().isoformat())
            self.assertEqual(metadata["config_path"], str(config_path))
            self.assertEqual(metadata["local_config_path"], str(local_config_path))

    def test_load_gmail_secret_config_prefers_project_env_local(self):
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
                config, secret_source, error = service_config.load_gmail_secret_config()

            self.assertIsNone(error)
            self.assertEqual(config["email"], "project@example.com")
            self.assertEqual(config["app_password"], "project-password")
            self.assertEqual(secret_source, str(project_env))

    def test_validate_service_config_reports_empty_recipients_and_missing_gmail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            repo_path = tmp_path / "asset_prices_repo"
            data_path = repo_path / "data"
            data_path.mkdir(parents=True)

            config = {
                "asset_prices": {
                    "repo_path": str(repo_path),
                    "data_dir": str(data_path),
                    "data_type": "adjusted",
                },
                "monitor": {
                    "symbol": "VOO",
                    "source": "alpaca",
                    "original_start": "2016-11-08",
                    "original_end": "2020-11-03",
                    "new_start": "2024-11-05",
                    "new_end": date.today().isoformat(),
                    "sma_window": 100,
                    "plot_bands": True,
                    "plot_bollinger_bands": False,
                    "check_frequency_minutes": 15,
                },
                "alerts": {"enabled": True, "recipients": []},
                "runtime": {
                    "html_output_path": "./plots/index.html",
                    "log_path": "./runtime/main.log",
                },
                "_metadata": {
                    "config_path": str(tmp_path / "service.json"),
                    "local_config_path": str(tmp_path / "service.local.json"),
                    "local_config_exists": True,
                },
            }

            issues = service_config.validate_service_config(
                config,
                gmail_config=None,
                require_gmail=True,
            )

            self.assertTrue(any("alerts.recipients" in issue for issue in issues))
            self.assertTrue(any("Gmail" in issue for issue in issues))

    def test_redact_service_config_removes_password_keys(self):
        redacted = service_config.redact_service_config(
            {
                "alerts": {"enabled": True, "recipients": ["ops@example.com"]},
                "runtime": {"app_password": "secret-value"},
                "GMAIL_APP_PASSWORD": "secret-value",
            },
            metadata={"secret_source": ".env.local"},
        )

        dumped = json.dumps(redacted)
        self.assertNotIn("GMAIL_APP_PASSWORD", dumped)
        self.assertNotIn("secret-value", dumped)
        self.assertEqual(redacted["metadata"]["secret_source"], ".env.local")


if __name__ == "__main__":
    unittest.main()
