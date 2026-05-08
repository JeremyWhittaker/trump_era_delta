import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import report_pipeline


class ReportPipelineTests(unittest.TestCase):
    def _truncated_reference_frame(self):
        return pd.DataFrame(
            {
                "index": pd.to_datetime(["2020-01-01"], utc=True),
                "adj_close": [100.0],
                "regression_line": [0.10],
                "regression_upper_band_1": [0.12],
                "regression_upper_band_2": [0.18],
                "regression_upper_band_3": [0.24],
                "regression_upper_band_4": [0.30],
                "regression_lower_band_1": [0.08],
                "regression_lower_band_2": [0.02],
                "regression_lower_band_3": [-0.04],
                "regression_lower_band_4": [-0.10],
            }
        )

    def _new_frame(self):
        return pd.DataFrame(
            {
                "index": pd.to_datetime(["2024-11-05"], utc=True),
                "adj_close": [123.45],
                "cumulative_pct_change": [0.15],
                "day_index": [0],
            }
        )

    def test_build_band_snapshot_returns_expected_keys_and_bands(self):
        snapshot = report_pipeline.build_band_snapshot(
            self._truncated_reference_frame(),
            self._new_frame(),
        )

        self.assertEqual(
            set(snapshot.keys()),
            {"current_band", "current_pct", "regression_line", "bands", "latest_price", "latest_date"},
        )
        self.assertEqual(snapshot["current_band"], 1)
        self.assertEqual(
            list(snapshot["bands"].keys()),
            ["+4σ", "+3σ", "+2σ", "+1σ", "avg", "-1σ", "-2σ", "-3σ", "-4σ"],
        )

    def test_generate_comparison_report_returns_artifact_paths_and_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            zoomed_path = tmp_path / "zoomed.jpeg"
            full_path = tmp_path / "full.jpeg"
            html_path = tmp_path / "report.html"

            with mock.patch.object(
                report_pipeline,
                "plot_comparison",
                return_value=(zoomed_path, full_path, html_path),
            ) as plot_comparison:
                result = report_pipeline.generate_comparison_report(
                    symbol="VOO",
                    source="alpaca",
                    df_original=self._truncated_reference_frame(),
                    df_original_truncated=self._truncated_reference_frame(),
                    df_new=self._new_frame(),
                    output_dir=tmp_path,
                    sma_window=100,
                    plot_bands=True,
                    plot_bollinger_bands=False,
                    original_start="2016-11-08",
                    original_end="2020-11-03",
                    new_start="2024-11-05",
                )

        self.assertEqual(
            set(result.keys()),
            {
                "zoomed_jpeg_path",
                "full_jpeg_path",
                "html_path",
                "data_freshness",
                "freshness_warning",
                "latest_data_age_days",
                "max_data_age_days",
                "freshness_checked_at",
                "current_band",
                "current_pct",
                "regression_line",
                "bands",
                "latest_price",
                "latest_date",
            },
        )
        self.assertEqual(result["zoomed_jpeg_path"], zoomed_path)
        self.assertEqual(result["full_jpeg_path"], full_path)
        self.assertEqual(result["html_path"], html_path)
        plot_comparison.assert_called_once()

    def test_generate_comparison_report_carries_freshness_metadata(self):
        data_freshness = {
            "warning": "Latest VOO alpaca bar is 3 calendar days old.",
            "age_days": 3,
            "max_age_days": 2,
            "checked_at": "2026-05-08T00:00:00+00:00",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with mock.patch.object(
                report_pipeline,
                "plot_comparison",
                return_value=(tmp_path / "zoomed.jpeg", tmp_path / "full.jpeg", tmp_path / "report.html"),
            ) as plot_comparison:
                result = report_pipeline.generate_comparison_report(
                    symbol="VOO",
                    source="alpaca",
                    df_original=self._truncated_reference_frame(),
                    df_original_truncated=self._truncated_reference_frame(),
                    df_new=self._new_frame(),
                    output_dir=tmp_path,
                    sma_window=100,
                    data_freshness=data_freshness,
                )

        self.assertEqual(result["data_freshness"], data_freshness)
        self.assertEqual(result["freshness_warning"], data_freshness["warning"])
        self.assertEqual(result["latest_data_age_days"], 3)
        self.assertEqual(result["max_data_age_days"], 2)
        self.assertEqual(result["freshness_checked_at"], data_freshness["checked_at"])
        self.assertEqual(
            plot_comparison.call_args.kwargs["data_freshness"],
            data_freshness,
        )


if __name__ == "__main__":
    unittest.main()
