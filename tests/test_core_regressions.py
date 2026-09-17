from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.group_layout import (
    PAGINATION_CONTINUOUS,
    PAGINATION_GROUPED,
    compute_page_ranges,
    effective_page_breaks,
    minimum_title_region_height_cm,
    resolve_title_vertical_geometry,
    shift_groups_for_delete,
    shift_groups_for_insert,
)
from core.project_manager import (
    load_project_file,
    normalize_project_path,
    save_project_file,
)
from core.drag_protocol import decode_drag_rows, encode_drag_rows


ROOT = Path(__file__).resolve().parents[1]


class PaginationRegressionTests(unittest.TestCase):
    def test_manual_break_starts_an_independent_page_segment(self):
        self.assertEqual(
            compute_page_ranges(9, 4, [3]),
            [(0, 3), (3, 7), (7, 9)],
        )

    def test_group_boundaries_apply_only_in_grouped_mode(self):
        groups = [
            {"id": "a", "name": "A", "start": 0},
            {"id": "b", "name": "B", "start": 3},
        ]
        self.assertEqual(
            effective_page_breaks([], groups, PAGINATION_CONTINUOUS, 8),
            [],
        )
        self.assertEqual(
            effective_page_breaks([], groups, PAGINATION_GROUPED, 8),
            [3],
        )

    def test_group_boundaries_shift_with_insert_and_delete(self):
        groups = [
            {"id": "a", "name": "A", "start": 0},
            {"id": "b", "name": "B", "start": 4},
        ]
        inserted = shift_groups_for_insert(groups, 2, 2, 8)
        self.assertEqual([item["start"] for item in inserted], [0, 6])
        deleted = shift_groups_for_delete(inserted, [1, 2], 10)
        self.assertEqual([item["start"] for item in deleted], [0, 4])


class TitleGeometryRegressionTests(unittest.TestCase):
    def test_large_font_expands_an_unsafe_title_region(self):
        geometry = resolve_title_vertical_geometry(
            {
                "font_size": 48,
                "bold": True,
                "top_spacing_cm": 0,
                "region_height_cm": 0.35,
            },
            enabled=True,
            has_content=True,
        )
        minimum = minimum_title_region_height_cm(48, True)
        self.assertGreater(minimum, 2.0)
        self.assertAlmostEqual(geometry["effective_height_cm"], minimum)
        self.assertTrue(geometry["auto_expanded"])

    def test_disabled_or_empty_title_reserves_no_space(self):
        for enabled, has_content in ((False, True), (True, False)):
            geometry = resolve_title_vertical_geometry(
                {"font_size": 48, "region_height_cm": 0.35},
                enabled=enabled,
                has_content=has_content,
            )
            self.assertEqual(geometry["effective_height_cm"], 0.0)
            self.assertEqual(geometry["effective_top_spacing_cm"], 0.0)


class ProjectFormatRegressionTests(unittest.TestCase):
    def test_minimal_fixture_is_v12_project(self):
        fixture = ROOT / "tests" / "fixtures" / "minimal_v12.fds"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        self.assertEqual(payload["format"], "FrameDeck Studio Project")
        self.assertEqual(payload["version"], 12)

    def test_project_round_trip_preserves_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "round_trip"
            with patch("core.project_manager.add_recent_project"):
                saved = save_project_file(str(target), {"images": ["a.png"]})
                loaded = load_project_file(saved)
        self.assertEqual(Path(saved).suffix, ".fds")
        self.assertEqual(loaded["version"], 12)
        self.assertEqual(loaded["images"], ["a.png"])

    def test_normalize_project_path_is_idempotent(self):
        self.assertEqual(normalize_project_path("demo.fds"), "demo.fds")
        self.assertEqual(normalize_project_path("demo"), "demo.fds")


class DragProtocolRegressionTests(unittest.TestCase):
    def test_rows_are_normalized_and_round_trip(self):
        payload = encode_drag_rows([4, "2", 4, -1, "bad"])
        self.assertEqual(decode_drag_rows(payload), [2, 4])

    def test_invalid_payload_is_rejected(self):
        self.assertEqual(decode_drag_rows(b"not-json"), [])


if __name__ == "__main__":
    unittest.main()
