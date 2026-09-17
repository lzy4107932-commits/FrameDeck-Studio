from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT_PATH = ROOT / "FrameDeck_UI05_51A_packaging_preflight.py"
SPEC = importlib.util.spec_from_file_location(
    "framedeck_packaging_preflight",
    PREFLIGHT_PATH,
)
PREFLIGHT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PREFLIGHT)


class PackagingPreflightTests(unittest.TestCase):
    def test_new_startup_error_window_is_detected(self):
        with patch.object(
            PREFLIGHT,
            "visible_window_titles",
            return_value={10: "Existing", 11: "Unhandled exception in script"},
        ):
            errors = PREFLIGHT.new_startup_error_windows({10: "Existing"})

        self.assertEqual(errors, {11: "Unhandled exception in script"})

    def test_preexisting_error_window_is_ignored(self):
        with patch.object(
            PREFLIGHT,
            "visible_window_titles",
            return_value={11: "Unhandled exception in script"},
        ):
            errors = PREFLIGHT.new_startup_error_windows(
                {11: "Unhandled exception in script"}
            )

        self.assertEqual(errors, {})

    def test_windows_smoke_cleanup_terminates_process_tree(self):
        class RunningProcess:
            pid = 321

            @staticmethod
            def poll():
                return None

        with (
            patch.object(PREFLIGHT.os, "name", "nt"),
            patch.object(PREFLIGHT.subprocess, "run") as run,
        ):
            PREFLIGHT.stop_smoke_process(RunningProcess())

        command = run.call_args.args[0]
        self.assertEqual(command[:3], ["taskkill", "/PID", "321"])
        self.assertIn("/T", command)
        self.assertIn("/F", command)


if __name__ == "__main__":
    unittest.main()
