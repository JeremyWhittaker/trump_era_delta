import tempfile
import unittest
from pathlib import Path

import alert_state


class AlertStateTests(unittest.TestCase):
    def test_resolve_alert_state_path_defaults_next_to_log_file(self):
        resolved = alert_state.resolve_alert_state_path(log_path="./runtime/main.log")
        self.assertEqual(resolved, Path("runtime") / "alert_state.json")

    def test_load_alert_state_returns_default_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state = alert_state.load_alert_state(Path(tmpdir) / "missing.json")

        self.assertEqual(state, alert_state.DEFAULT_ALERT_STATE)

    def test_load_alert_state_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "alert_state.json"
            state_path.write_text("[1, 2, 3]\n", encoding="utf-8")

            with self.assertRaises(ValueError) as exc:
                alert_state.load_alert_state(state_path)

        self.assertIn("JSON object", str(exc.exception))

    def test_save_and_load_round_trip_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "alert_state.json"
            state = {
                "last_observed_band": 1,
                "pending_transition": {
                    "from_band": 0,
                    "to_band": 1,
                    "observed_at": "2026-04-20T00:00:00+00:00",
                },
                "last_delivered_transition": None,
                "pending_monthly_update": {
                    "month": "2026-06",
                    "observed_at": "2026-06-01T00:00:00+00:00",
                },
                "last_monthly_update": None,
                "last_error": "smtp failed",
            }

            alert_state.save_alert_state(state_path, state)
            loaded = alert_state.load_alert_state(state_path)

        self.assertEqual(loaded["last_observed_band"], 1)
        self.assertEqual(loaded["pending_transition"]["to_band"], 1)
        self.assertEqual(loaded["pending_monthly_update"]["month"], "2026-06")
        self.assertEqual(loaded["last_error"], "smtp failed")

    def test_delivered_transition_is_not_reemitted_after_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "alert_state.json"
            state = alert_state.load_alert_state(state_path)
            first_observation = alert_state.evaluate_transition(
                state,
                current_band=0,
                observed_at="2026-04-20T00:00:00+00:00",
            )["state"]
            second_observation = alert_state.evaluate_transition(
                first_observation,
                current_band=1,
                observed_at="2026-04-20T00:05:00+00:00",
            )
            delivered_state = alert_state.record_delivery_result(
                second_observation["state"],
                second_observation["transition"],
                delivered=True,
            )
            alert_state.save_alert_state(state_path, delivered_state)
            reloaded = alert_state.load_alert_state(state_path)
            next_result = alert_state.evaluate_transition(
                reloaded,
                current_band=1,
                observed_at="2026-04-20T00:10:00+00:00",
            )

        self.assertEqual(next_result["action"], "no_change")
        self.assertIsNone(next_result["transition"])

    def test_failed_delivery_stays_pending_and_retries_after_reload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "alert_state.json"
            state = alert_state.load_alert_state(state_path)
            first_observation = alert_state.evaluate_transition(
                state,
                current_band=0,
                observed_at="2026-04-20T00:00:00+00:00",
            )["state"]
            second_observation = alert_state.evaluate_transition(
                first_observation,
                current_band=1,
                observed_at="2026-04-20T00:05:00+00:00",
            )
            failed_state = alert_state.record_delivery_result(
                second_observation["state"],
                second_observation["transition"],
                delivered=False,
                error_message="smtp failed",
            )
            alert_state.save_alert_state(state_path, failed_state)
            reloaded = alert_state.load_alert_state(state_path)
            retry_result = alert_state.evaluate_transition(
                reloaded,
                current_band=1,
                observed_at="2026-04-20T00:10:00+00:00",
            )

        self.assertEqual(retry_result["action"], "retry_pending")
        self.assertEqual(retry_result["transition"]["from_band"], 0)
        self.assertEqual(retry_result["transition"]["to_band"], 1)

    def test_monthly_update_is_due_on_first_day_and_not_reemitted_after_delivery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "alert_state.json"
            state = alert_state.load_alert_state(state_path)
            result = alert_state.evaluate_monthly_update(
                state,
                observed_at="2026-06-01T00:00:00+00:00",
            )

            delivered_state = alert_state.record_monthly_update_result(
                result["state"],
                result["monthly_update"],
                delivered=True,
            )
            alert_state.save_alert_state(state_path, delivered_state)
            reloaded = alert_state.load_alert_state(state_path)
            next_result = alert_state.evaluate_monthly_update(
                reloaded,
                observed_at="2026-06-01T00:15:00+00:00",
            )

        self.assertEqual(result["action"], "new_monthly_update")
        self.assertEqual(result["monthly_update"]["month"], "2026-06")
        self.assertEqual(next_result["action"], "already_delivered")
        self.assertIsNone(next_result["monthly_update"])

    def test_failed_monthly_update_retries_on_same_first_day(self):
        state = alert_state.DEFAULT_ALERT_STATE
        result = alert_state.evaluate_monthly_update(
            state,
            observed_at="2026-06-01T00:00:00+00:00",
        )
        failed_state = alert_state.record_monthly_update_result(
            result["state"],
            result["monthly_update"],
            delivered=False,
            error_message="smtp failed",
        )
        retry_result = alert_state.evaluate_monthly_update(
            failed_state,
            observed_at="2026-06-01T00:15:00+00:00",
        )

        self.assertEqual(retry_result["action"], "retry_pending")
        self.assertEqual(retry_result["monthly_update"]["month"], "2026-06")
        self.assertEqual(retry_result["monthly_update"]["last_error"], "smtp failed")

    def test_monthly_update_is_not_due_after_first_day(self):
        result = alert_state.evaluate_monthly_update(
            alert_state.DEFAULT_ALERT_STATE,
            observed_at="2026-06-02T00:00:00+00:00",
        )

        self.assertEqual(result["action"], "not_due")
        self.assertIsNone(result["monthly_update"])


if __name__ == "__main__":
    unittest.main()
