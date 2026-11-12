"""Caption timing is the part users notice first — it must survive the cut."""
import tempfile
import unittest
from pathlib import Path

from shortsforge import render


class TestRemapCues(unittest.TestCase):
    def test_shifts_cue_by_the_time_removed_before_it(self):
        cues = [{"start": 10, "end": 11, "text": "hello"}]
        out = render.remap_cues(cues, [(0, 5), (9, 15)])
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0]["start"], 6.0)
        self.assertAlmostEqual(out[0]["end"], 7.0)

    def test_splits_a_cue_that_spans_a_removed_gap(self):
        cues = [{"start": 4, "end": 12, "text": "straddle"}]
        out = render.remap_cues(cues, [(0, 5), (10, 15)], min_piece=0.1)
        self.assertEqual([round(c["start"], 2) for c in out], [4.0, 5.0])
        self.assertAlmostEqual(out[0]["end"], 5.0)
        self.assertAlmostEqual(out[1]["end"], 7.0)

    def test_clips_a_cue_that_overruns_the_keep_range(self):
        cues = [{"start": 4, "end": 6, "text": "tail"}]
        out = render.remap_cues(cues, [(0, 5), (10, 15)], min_piece=0.1)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0]["end"], 5.0)

    def test_drops_cues_that_land_entirely_in_removed_audio(self):
        cues = [{"start": 6, "end": 8, "text": "gone"}]
        self.assertEqual(render.remap_cues(cues, [(0, 5), (10, 15)]), [])

    def test_output_is_sorted_by_start(self):
        cues = [{"start": 12, "end": 13, "text": "b"}, {"start": 1, "end": 2, "text": "a"}]
        self.assertEqual([c["text"] for c in render.remap_cues(cues, [(0, 20)])], ["a", "b"])


class TestWrap(unittest.TestCase):
    def test_breaks_long_text_into_lines(self):
        self.assertEqual(render.wrap("一二三四五六七", 4).count("\\N"), 1)

    def test_prefers_punctuation_boundary(self):
        self.assertEqual(render.wrap("你好，世界你好", 5), "你好，\\N世界你好")

    def test_leaves_short_text_alone(self):
        self.assertEqual(render.wrap("短句", 15), "短句")

    def test_never_slices_a_latin_or_digit_token(self):
        out = render.wrap("这是自动字幕测试，shortsforge 1080x1920", 13)
        self.assertNotIn("1\\N080", out)
        self.assertIn("shortsforge", out.replace("\\N", " "))
        self.assertTrue(out.split("\\N")[-1].startswith("1080x1920"))


class TestAssFile(unittest.TestCase):
    def test_writes_a_valid_header_and_one_dialogue_per_cue(self):
        style = render.load_style("douyin_fast")
        with tempfile.TemporaryDirectory() as d:
            path = render.build_ass(
                [{"start": 0, "end": 1.5, "text": "测试"}], style, Path(d) / "c.ass"
            )
            body = path.read_text(encoding="utf-8")
        assert body.startswith("[Script Info]")
        assert "PlayResX: 1080" in body and "PlayResY: 1920" in body
        assert body.count("Dialogue:") == 1
        assert "0:00:00.00,0:00:01.50" in body

    def test_rejects_unknown_style_keys(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"
            p.write_text(json.dumps({"font_sise": 40}), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                render.load_style(str(p))


if __name__ == "__main__":
    unittest.main()
