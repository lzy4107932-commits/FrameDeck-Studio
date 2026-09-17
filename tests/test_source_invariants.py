from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_SOURCE_DIRS = (ROOT / "core", ROOT / "gui")


class SourceInvariantTests(unittest.TestCase):
    def test_active_python_sources_compile(self):
        paths = [ROOT / "main.py"]
        for directory in ACTIVE_SOURCE_DIRS:
            paths.extend(directory.glob("*.py"))
        for path in paths:
            with self.subTest(path=path.relative_to(ROOT)):
                source = path.read_text(encoding="utf-8-sig")
                compile(source, str(path), "exec")

    def test_preview_drag_handlers_are_class_methods(self):
        source = (ROOT / "gui" / "main_window.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertNotIn("PreviewCanvas.dragEnterEvent =", source)
        self.assertNotIn("PreviewCanvas.dragMoveEvent =", source)
        self.assertNotIn("PreviewCanvas.dragLeaveEvent =", source)
        self.assertNotIn("PreviewCanvas.dropEvent =", source)

        preview_source = (ROOT / "gui" / "preview_widget.py").read_text(
            encoding="utf-8-sig"
        )
        tree = ast.parse(preview_source)
        preview_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "PreviewCanvas"
        )
        methods = {
            node.name for node in preview_class.body if isinstance(node, ast.FunctionDef)
        }
        self.assertTrue(
            {"dragEnterEvent", "dragMoveEvent", "dragLeaveEvent", "dropEvent"}
            <= methods
        )

    def test_drag_protocol_has_one_mime_and_no_legacy_wrappers(self):
        main_source = (ROOT / "gui" / "main_window.py").read_text(
            encoding="utf-8-sig"
        )
        preview_source = (ROOT / "gui" / "preview_widget.py").read_text(
            encoding="utf-8-sig"
        )
        protocol_source = (ROOT / "core" / "drag_protocol.py").read_text(
            encoding="utf-8-sig"
        )
        corpus = main_source + preview_source + protocol_source
        self.assertEqual(corpus.count("application/x-framedeck-current-page-drag-v2"), 1)
        self.assertNotIn("application/x-framedeck-image-list-rows", corpus)
        self.assertNotIn("_FD_UI0545C_PREVIEW_DRAG_ENTER_ORIGINAL", corpus)
        self.assertNotIn("_fd_ui0550a_fix02_drag_enter", corpus)

    def test_removed_modules_are_not_referenced(self):
        paths = [ROOT / "main.py"]
        paths.extend((ROOT / "core").glob("*.py"))
        paths.extend((ROOT / "gui").glob("*.py"))
        corpus = "\n".join(path.read_text(encoding="utf-8-sig") for path in paths)
        self.assertNotIn("from core.page_thumbnail_renderer import", corpus)
        self.assertNotIn("from gui.slide_thumbnail import", corpus)
        self.assertNotIn("PageManager", corpus)

    def test_packaging_includes_templates_and_heif(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8-sig")
        spec = (ROOT / "FrameDeck Studio V12 Stable.spec").read_text(encoding="utf-8-sig")
        self.assertIn("pillow-heif", requirements.lower())
        self.assertIn("('Template', 'Template')", spec)
        self.assertIn("collect_all('pillow_heif')", spec)

    def test_packaging_isolates_dll_search_and_checks_windows(self):
        for name in ("build_exe.bat", "build_portable_exe.bat"):
            source = (ROOT / name).read_text(encoding="utf-8-sig").lower()
            self.assertIn("python_exe", source)
            self.assertIn('set "path=%systemroot%\\system32;', source)

        preflight = (
            ROOT / "FrameDeck_UI05_51A_packaging_preflight.py"
        ).read_text(encoding="utf-8-sig")
        self.assertIn("STARTUP_ERROR_TITLE_MARKERS", preflight)
        self.assertIn("def new_startup_error_windows(before_handles):", preflight)
        self.assertIn("def stop_smoke_process(process):", preflight)
        self.assertIn('"/T",', preflight)
        self.assertIn("主窗口持续显示3秒", preflight)

    def test_thumbnail_refresh_builds_one_shared_signature_context(self):
        source = (ROOT / "gui" / "main_window.py").read_text(
            encoding="utf-8-sig"
        )
        tree = ast.parse(source)
        main_class = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "MainWindow"
        )
        methods = {
            node.name: node for node in main_class.body if isinstance(node, ast.FunctionDef)
        }

        preview_settings_source = ast.get_source_segment(
            source, methods["preview_settings"]
        )
        refresh_source = ast.get_source_segment(
            source, methods["refresh_real_page_thumbnails"]
        )
        signature_map_source = ast.get_source_segment(
            source, methods["_page_thumbnail_signature_map"]
        )

        self.assertEqual(preview_settings_source.count("_resolved_title_pages()"), 1)
        self.assertIn("_page_thumbnail_signature_map(count)", refresh_source)
        self.assertEqual(signature_map_source.count("_thumbnail_signature_context()"), 1)

    def test_batch_delete_does_not_replace_instance_methods(self):
        source = (ROOT / "gui" / "main_window.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertNotIn("self.push_history = (\n        lambda", source)
        self.assertNotIn("self.schedule_real_thumbnail_refresh = (\n        lambda", source)
        self.assertIn("record_history=False", source)
        self.assertIn("_thumbnail_refresh_suspended", source)

    def test_language_runtime_is_event_driven(self):
        source = (ROOT / "gui" / "main_window.py").read_text(
            encoding="utf-8-sig"
        )
        navigator_source = (ROOT / "gui" / "slide_thumbnail_bar.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertNotIn("_language_refresh_timer", source)
        self.assertNotIn("setInterval(450)", source)
        self.assertNotIn("_fd_ui0550a_fix01", source)
        self.assertIn("_queue_widget_translation(root)", source)
        self.assertIn("self._sync_import_button_language()", source)
        self.assertIn("QEvent.Type.ShowToParent", source)
        self.assertIn("QListWidget#PageNavigatorList", source)
        self.assertNotIn("setStyleSheet(", navigator_source)

    def test_preview_refresh_coalesces_config_writes(self):
        source = (ROOT / "gui" / "main_window.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("self._config_save_timer.setInterval(400)", source)
        self.assertIn("def request_config_save(self):", source)
        self.assertIn("if config_text == self._last_config_text:", source)
        self.assertIn("effective_breaks = self._effective_page_breaks(image_count)", source)

    def test_release_tools_match_the_clean_baseline(self):
        regression = (ROOT / "FrameDeck_UI05_50C_release_regression_check.py").read_text(
            encoding="utf-8-sig"
        )
        packaging = (ROOT / "FrameDeck_UI05_51A_packaging_preflight.py").read_text(
            encoding="utf-8-sig"
        )
        baseline = (ROOT / "CURRENT_STABLE_BASELINE.txt").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("ACTIVE_RELEASE_TOOLS", regression)
        self.assertIn("PreviewCanvas 使用正式拖放实现", regression)
        self.assertIn('"--check"', packaging)
        self.assertIn('or "iscc"', packaging)
        self.assertIn("FrameDeck Studio Stable Clean Baseline", baseline)

    def test_minimum_width_header_hides_only_redundant_badges(self):
        source = (ROOT / "gui" / "main_window.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("def _update_responsive_header(self):", source)
        self.assertIn("show_redundant_badges = self.width() >= 1180", source)
        self.assertIn('("header_layout_badge", "header_project_badge")', source)
        self.assertIn("title.setVisible(show_redundant_badges)", source)
        self.assertIn("subtitle.setVisible(show_redundant_badges)", source)

    def test_empty_canvas_has_bilingual_start_guidance(self):
        source = (ROOT / "gui" / "preview_widget.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("if not self._images and not self._navigation_thumbnail_mode:", source)
        self.assertIn("Add images or drop them here", source)
        self.assertIn("添加图片，或将图片拖到此处", source)
        self.assertIn("def set_language(self, language: str):", source)

    def test_large_thumbnail_work_is_batched(self):
        source = (ROOT / "gui" / "main_window.py").read_text(
            encoding="utf-8-sig"
        )
        navigator = (ROOT / "gui" / "slide_thumbnail_bar.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("self._thumbnail_priority_dirty = True", source)
        self.assertIn("if not self._thumbnail_priority_dirty:", source)
        self.assertIn("schedule_dispatch=False", source)
        self.assertIn("def _flush_navigation_thumbnail_invalidations(self):", source)
        self.assertIn("self._thumbnail_navigation_flush_timer.setInterval(160)", source)
        self.assertIn("self._page_sources[index] = pixmap", navigator)
        self.assertIn("self.setUniformItemSizes(True)", navigator)
        self.assertIn("self.setLayoutMode(QListView.LayoutMode.Batched)", navigator)

    def test_project_image_clipboard_pastes_independent_assets(self):
        source = (ROOT / "gui" / "main_window.py").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("self._image_clipboard = []", source)
        self.assertIn("def shortcut_copy_images(self):", source)
        self.assertIn("def paste_images_to_current_page(self):", source)
        self.assertIn('"transform": dict(self.get_transform', source)
        self.assertIn("destination = self._unique_copy_path(source)", source)
        self.assertIn('"粘贴图片"', source)
        self.assertIn("Ctrl+C", source)
        self.assertIn("Ctrl+V", source)

    def test_ppt_export_uses_only_editable_native_crop(self):
        source = (ROOT / "core" / "ppt_generator.py").read_text(
            encoding="utf-8-sig"
        )
        tree = ast.parse(source)
        generate = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "generate_ppt"
        )
        generate_source = ast.get_source_segment(source, generate)
        self.assertIn("_add_editable_picture(", generate_source)
        self.assertIn("_render_full_editable_source(", generate_source)
        self.assertNotIn("_add_compatibility_picture(", generate_source)
        self.assertNotIn("_render_image_box(", generate_source)


if __name__ == "__main__":
    unittest.main()
