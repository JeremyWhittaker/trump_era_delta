import tempfile
import unittest
from datetime import date
from pathlib import Path
from contextlib import redirect_stdout
import importlib
import io
import sys
from unittest import mock

from service_bootstrap import build_preflight_report, load_asset_prices_reader


class ServiceBootstrapTests(unittest.TestCase):
    def test_load_asset_prices_reader_reports_missing_repo(self):
        reader, error = load_asset_prices_reader("/tmp/does-not-exist-for-trump-era-delta")
        self.assertIsNone(reader)
        self.assertIn("does not exist", error)

    def test_build_preflight_report_includes_validation_and_import_errors(self):
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
                "_metadata": {"local_config_exists": True},
            }

            report = build_preflight_report(
                config,
                {"config_path": "config/service.json", "local_config_path": "config/service.local.json"},
                gmail_config=None,
                require_gmail=True,
            )

            self.assertFalse(report["ok"])
            self.assertTrue(any("alerts.recipients" in error for error in report["errors"]))
            self.assertTrue(any("Gmail" in error for error in report["errors"]))
            self.assertTrue(any("Unable to import" in error for error in report["errors"]))


class MainCliTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("main", None)

    def _load_main(self):
        return importlib.import_module("main")

    def _valid_config(self, tmp_path, alerts_enabled=True):
        repo_path = tmp_path / "asset_prices_repo"
        data_path = repo_path / "data"
        data_path.mkdir(parents=True)
        return {
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
            "alerts": {"enabled": alerts_enabled, "recipients": ["ops@example.com"]},
            "runtime": {
                "html_output_path": "./plots/index.html",
                "log_path": "./runtime/main.log",
            },
            "_metadata": {"local_config_exists": True},
        }

    def test_main_help_lists_subcommands(self):
        main = self._load_main()
        output = io.StringIO()
        with self.assertRaises(SystemExit) as exc, redirect_stdout(output):
            main.main(["--help"])

        self.assertEqual(exc.exception.code, 0)
        help_text = output.getvalue()
        self.assertIn("check", help_text)
        self.assertIn("run", help_text)
        self.assertIn("test-email", help_text)
        self.assertIn("show-config", help_text)

    def test_run_does_not_call_main_loop_when_preflight_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main = self._load_main()
            config = self._valid_config(Path(tmpdir))

            with mock.patch.object(main, "load_service_config", return_value=(config, {}, None)), mock.patch.object(
                main, "load_gmail_secret_config", return_value=(None, None, "bad gmail")
            ), mock.patch.object(
                main,
                "build_preflight_report",
                return_value={"ok": False, "errors": ["bad config"], "warnings": [], "paths": {}},
            ), mock.patch.object(main, "print_preflight_report"), mock.patch.object(main, "main_loop") as main_loop:
                exit_code = main.main(["run"])

            self.assertEqual(exit_code, 1)
            main_loop.assert_not_called()

    def test_test_email_does_not_call_send_when_preflight_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main = self._load_main()
            config = self._valid_config(Path(tmpdir))

            with mock.patch.object(main, "load_service_config", return_value=(config, {}, None)), mock.patch.object(
                main, "load_gmail_secret_config", return_value=(None, None, "bad gmail")
            ), mock.patch.object(
                main,
                "build_preflight_report",
                return_value={"ok": False, "errors": ["bad config"], "warnings": [], "paths": {}},
            ), mock.patch.object(main, "print_preflight_report"), mock.patch.object(
                main, "send_test_email_now"
            ) as send_test_email_now:
                exit_code = main.main(["test-email"])

            self.assertEqual(exit_code, 1)
            send_test_email_now.assert_not_called()

    def test_show_config_redacts_password_and_reports_secret_source(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            main = self._load_main()
            config = self._valid_config(Path(tmpdir))

            output = io.StringIO()
            with mock.patch.object(main, "load_service_config", return_value=(config, {}, None)), mock.patch.object(
                main,
                "load_gmail_secret_config",
                return_value=({"email": "sender@example.com", "app_password": "secret-value"}, ".env.local", None),
            ), redirect_stdout(output):
                exit_code = main.main(["show-config", "--json"])

            rendered = output.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("ops@example.com", rendered)
            self.assertIn(".env.local", rendered)
            self.assertNotIn("secret-value", rendered)


if __name__ == "__main__":
    unittest.main()
