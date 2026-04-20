import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import alert_pipeline


class AlertPipelineTests(unittest.TestCase):
    def _report(self, tmp_path):
        zoomed_path = tmp_path / "zoomed.jpeg"
        full_path = tmp_path / "full.jpeg"
        zoomed_path.write_bytes(b"zoomed-bytes")
        full_path.write_bytes(b"full-bytes")
        return {
            "zoomed_jpeg_path": zoomed_path,
            "full_jpeg_path": full_path,
            "latest_date": datetime(2026, 4, 20, 12, 30, tzinfo=timezone.utc),
            "latest_price": 123.45,
            "current_band": 1,
            "current_pct": 0.15,
            "regression_line": 0.10,
            "bands": {
                "+4σ": 0.30,
                "+3σ": 0.24,
                "+2σ": 0.18,
                "+1σ": 0.12,
                "avg": 0.10,
                "-1σ": 0.08,
                "-2σ": 0.02,
                "-3σ": -0.04,
                "-4σ": -0.10,
            },
        }

    def test_build_alert_payload_reuses_same_body_and_inline_images_for_test_and_live(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report = self._report(Path(tmpdir))

            live_payload = alert_pipeline.build_alert_payload(
                symbol="VOO",
                source="alpaca",
                previous_band=1,
                report=report,
                days_original=100,
                days_new=50,
                sma_window=100,
                check_frequency=15,
                original_start="2016-11-08",
                original_end="2020-11-03",
                new_start="2024-11-05",
                delivery_mode="live",
            )
            test_payload = alert_pipeline.build_alert_payload(
                symbol="VOO",
                source="alpaca",
                previous_band=1,
                report=report,
                days_original=100,
                days_new=50,
                sma_window=100,
                check_frequency=15,
                original_start="2016-11-08",
                original_end="2020-11-03",
                new_start="2024-11-05",
                delivery_mode="test",
            )

        self.assertEqual(live_payload["html_body"], test_payload["html_body"])
        self.assertEqual(live_payload["text_body"], test_payload["text_body"])
        self.assertEqual(live_payload["inline_images"], test_payload["inline_images"])
        self.assertEqual(
            [image["cid"] for image in live_payload["inline_images"]],
            ["chart_zoomed", "chart_full"],
        )
        self.assertEqual(live_payload["subject"], "Regression Band Alert: VOO -> +1σ")
        self.assertEqual(test_payload["subject"], "TEST EMAIL: VOO @ +1σ (+15.00%)")

    def test_send_alert_email_forwards_normalized_payload_to_smtp(self):
        payload = {
            "subject": "Regression Band Alert: VOO -> +1σ",
            "html_body": "<p>html</p>",
            "text_body": "text",
            "inline_images": [{"cid": "chart_zoomed", "content": b"123", "subtype": "jpeg"}],
        }

        with mock.patch.object(
            alert_pipeline, "send_email", return_value=(True, "ok")
        ) as send_email:
            result = alert_pipeline.send_alert_email(
                recipients=["ops@example.com"],
                payload=payload,
            )

        self.assertEqual(result, (True, "ok"))
        send_email.assert_called_once_with(
            to_addrs=["ops@example.com"],
            subject="Regression Band Alert: VOO -> +1σ",
            body=None,
            html_body="<p>html</p>",
            text_body="text",
            inline_images=[{"cid": "chart_zoomed", "content": b"123", "subtype": "jpeg"}],
        )


if __name__ == "__main__":
    unittest.main()
