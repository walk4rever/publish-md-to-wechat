#!/usr/bin/env python3
"""Offline tests for the HTML/FFmpeg video pipeline."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from video_pipeline import (
    build_timeline,
    create_video_project,
    parse_scenes,
    render_ass,
    validate_target_duration,
    validate_scene_html,
)


class TestScenes(unittest.TestCase):
    def test_parse_scenes_requires_ordered_unique_ids(self):
        scenes = parse_scenes("S1|第一句\nS2|第二句\n")
        self.assertEqual([scene.id for scene in scenes], ["S1", "S2"])
        self.assertEqual(scenes[0].spoken_text, "第一句")

        with self.assertRaises(ValueError):
            parse_scenes("S1|第一句\nS1|重复\n")
        with self.assertRaises(ValueError):
            parse_scenes("S2|跳过开场\n")

    def test_validate_scene_html_reports_missing_file(self):
        scenes = parse_scenes("S1|第一句\nS2|第二句\n")
        with tempfile.TemporaryDirectory() as directory:
            open(os.path.join(directory, "S1.html"), "w", encoding="utf-8").close()
            with self.assertRaisesRegex(ValueError, "S2.html"):
                validate_scene_html(directory, scenes)


class TestTimelineAndSubtitles(unittest.TestCase):
    def test_timeline_adds_breathing_room(self):
        scenes = parse_scenes("S1|第一句\nS2|第二句\n")
        timeline = build_timeline(scenes, [2.0, 3.25], breathing_seconds=0.5)
        self.assertEqual(timeline[0].start, 0.0)
        self.assertEqual(timeline[0].duration, 2.5)
        self.assertEqual(timeline[1].start, 2.5)
        self.assertEqual(timeline[1].duration, 3.75)

    def test_target_duration_rejects_outside_tolerance(self):
        scenes = parse_scenes("S1|第一句\n")
        timeline = build_timeline(scenes, [30.0])
        self.assertTrue(validate_target_duration(timeline, target_seconds=30, tolerance=0.1))
        self.assertFalse(validate_target_duration(timeline, target_seconds=60, tolerance=0.1))

    def test_render_ass_uses_display_text_and_safe_line_breaks(self):
        scenes = parse_scenes("S1|口播文字|字幕显示的规范域名 buffett.air7.fun\n")
        timeline = build_timeline(scenes, [4.0])
        ass = render_ass(timeline)
        self.assertIn("PingFang SC", ass)
        self.assertIn("buffett.air7.fun", ass)
        self.assertNotIn("口播文字", ass)
        self.assertIn("0:00:00.20", ass)


class TestVideoPublisherCli(unittest.TestCase):
    def test_create_video_project_copies_editable_template(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "video"
            create_video_project(project)
            self.assertTrue((project / "scenes.txt").is_file())
            generator = (project / "gen_scenes.py").read_text(encoding="utf-8")
            self.assertIn("DEFAULT_BRAND", generator)

    def test_dry_run_accepts_agent_video_project(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "scenes.txt").write_text("S1|第一句\n", encoding="utf-8")
            (project / "gen_scenes.py").write_text(
                "from pathlib import Path\n"
                "output = Path('scenes'); output.mkdir()\n"
                "(output / 'S1.html').write_text('<!doctype html><title>scene</title>')\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, os.path.join(os.path.dirname(__file__), "..", "scripts", "video_publisher.py"),
                 "--project-dir", str(project), "--out", str(project / "video.mp4"), "--duration", "30", "--dry-run"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("Validated 1 scenes", result.stdout)


if __name__ == "__main__":
    unittest.main()
