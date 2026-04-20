import unittest

import pandas as pd

import analysis_core


class AnalysisCoreTests(unittest.TestCase):
    def _price_frame(self):
        return pd.DataFrame(
            {
                "timestamp": pd.to_datetime(
                    ["2020-01-03", "2020-01-01", "2020-01-02"],
                    utc=True,
                ),
                "close": [103.0, 100.0, 101.0],
            }
        )

    def test_load_price_history_normalizes_datetime_and_adj_close(self):
        def fake_reader(**_kwargs):
            return self._price_frame()

        result = analysis_core.load_price_history(
            symbol="VOO",
            source="alpaca",
            data_dir=".",
            read_symbol_data_fn=fake_reader,
        )

        self.assertEqual(list(result.columns), ["index", "adj_close"])
        self.assertEqual(
            result["index"].dt.strftime("%Y-%m-%d").tolist(),
            ["2020-01-01", "2020-01-02", "2020-01-03"],
        )
        self.assertEqual(result["adj_close"].tolist(), [100.0, 101.0, 103.0])

    def test_load_price_history_rejects_missing_adj_close(self):
        def fake_reader(**_kwargs):
            return pd.DataFrame(
                {
                    "timestamp": pd.to_datetime(["2020-01-01", "2020-01-02"], utc=True),
                    "open": [100.0, 101.0],
                }
            )

        with self.assertRaises(ValueError) as exc:
            analysis_core.load_price_history(
                symbol="VOO",
                source="alpaca",
                data_dir=".",
                read_symbol_data_fn=fake_reader,
            )

        self.assertIn("Missing `adj_close` column", str(exc.exception))

    def test_calculate_regression_bands_adds_expected_columns(self):
        frame = pd.DataFrame(
            {
                "day_index": [0, 1, 2, 3],
                "cumulative_pct_change": [0.0, 0.01, 0.03, 0.02],
            }
        )

        result = analysis_core.calculate_regression_bands(frame)

        self.assertIn("regression_line", result.columns)
        self.assertIn("residual_std", result.columns)
        self.assertIn("regression_upper_band_4", result.columns)
        self.assertIn("regression_lower_band_4", result.columns)

    def test_prepare_analysis_frames_rejects_short_reference_window(self):
        frame = pd.DataFrame(
            {
                "index": pd.to_datetime(["2020-01-01", "2020-01-02"], utc=True),
                "adj_close": [100.0, 101.0],
            }
        )

        with self.assertRaises(ValueError) as exc:
            analysis_core.prepare_analysis_frames(
                df=frame,
                symbol="VOO",
                original_start="2020-01-01",
                original_end="2020-01-01",
                new_start="2020-01-02",
                adjusted_new_end="2020-01-02",
                sma_window=10,
                plot_bollinger_bands=False,
            )

        self.assertIn("Reference period produced only 1 row(s)", str(exc.exception))

    def test_prepare_aligned_period_returns_percent_and_day_index_columns(self):
        frame = pd.DataFrame(
            {
                "index": pd.to_datetime(
                    ["2020-01-01", "2020-01-02", "2020-01-03"],
                    utc=True,
                ),
                "adj_close": [100.0, 110.0, 121.0],
            }
        )

        result = analysis_core.prepare_aligned_period(frame, "2020-01-01", "2020-01-03")

        self.assertEqual(result["day_index"].tolist(), [0, 1, 2])
        self.assertIn("daily_pct_change", result.columns)
        self.assertIn("cumulative_pct_change", result.columns)
        self.assertEqual(result["daily_pct_change"].round(2).tolist(), [0.0, 10.0, 10.0])
        self.assertEqual(result["cumulative_pct_change"].round(2).tolist(), [0.0, 10.0, 20.0])


if __name__ == "__main__":
    unittest.main()
