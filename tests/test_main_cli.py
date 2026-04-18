import tempfile
import unittest
from datetime import date
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
