"""The planning rules decide what the audience actually sees — pin them down."""
import unittest

from shortsforge import plan


class TestMerge(unittest.TestCase):
    def test_joins_ranges_closer_than_gap(self):
        self.assertEqual(plan.merge([(0, 1), (1.1, 2)], gap=0.2), [(0, 2)])

    def test_keeps_ranges_farther_apart_than_gap(self):
        self.assertEqual(plan.merge([(0, 1), (2, 3)], gap=0.2), [(0, 1), (2, 3)])

    def test_sorts_before_merging(self):
        self.assertEqual(plan.merge([(2, 3), (0, 1)], gap=0.2), [(0, 1), (2, 3)])


class TestSpeechFromSilence(unittest.TestCase):
    def test_inverts_a_middle_silence(self):
        ranges = plan.speech_from_silence(10, [(3, 5)], edge=0.1)
        self.assertEqual(ranges, [(0, 3.1), (4.9, 10)])

    def test_trailing_silence_runs_to_the_end(self):
        ranges = plan.speech_from_silence(10, [(8, None)], edge=0.0)
        self.assertEqual(ranges, [(0, 8)])

    def test_leading_silence_does_not_produce_empty_range(self):
        ranges = plan.speech_from_silence(10, [(0, 2)], edge=0.0)
        self.assertEqual(ranges, [(2, 10)])

    def test_fully_silent_clip_keeps_nothing(self):
        self.assertEqual(plan.speech_from_silence(10, [(0, 10)], edge=0.0), [])


class TestSegmentsToRanges(unittest.TestCase):
    def test_merge_small_pauses_and_keep_big_ones(self):
        segs = [{"start": 0, "end": 2, "text": "a"}, {"start": 2.1, "end": 4, "text": "b"}]
        self.assertEqual(plan.segments_to_ranges(segs, pad=0, gap=0.25), [(0, 4)])

        segs = [{"start": 0, "end": 2, "text": "a"}, {"start": 5, "end": 7, "text": "b"}]
        self.assertEqual(plan.segments_to_ranges(segs, pad=0, gap=0.25), [(0, 2), (5, 7)])

    def test_clamps_to_duration(self):
        segs = [{"start": 8, "end": 10, "text": "a"}]
        self.assertEqual(plan.segments_to_ranges(segs, pad=1, gap=0, duration=10), [(7, 10)])


class TestPickWindow(unittest.TestCase):
    def seg(self, start, end, n):
        return {"start": start, "end": end, "text": "字" * n}

    def test_returns_everything_when_it_fits(self):
        segs = [self.seg(0, 1, 5), self.seg(1, 2, 5)]
        self.assertEqual(plan.pick_window(segs, max_dur=10), segs)

    def test_prefers_more_characters_over_earlier_start(self):
        segs = [self.seg(0, 5, 1), self.seg(6, 7, 10), self.seg(7, 8, 10)]
        picked = plan.pick_window(segs, max_dur=3)
        self.assertEqual(picked, segs[1:])

    def test_never_returns_a_window_longer_than_max_dur(self):
        segs = [self.seg(i, i + 1, 5) for i in range(10)]
        picked = plan.pick_window(segs, max_dur=4)
        self.assertLessEqual(picked[-1]["end"] - picked[0]["start"], 4)


class TestClamp(unittest.TestCase):
    def test_trims_the_tail(self):
        self.assertEqual(plan.clamp([(0, 5), (10, 20)], max_dur=8), [(0, 5), (10, 13)])

    def test_drops_ranges_once_budget_is_spent(self):
        self.assertEqual(plan.clamp([(0, 5), (10, 12)], max_dur=5), [(0, 5)])

    def test_total_matches(self):
        ranges = [(0, 3), (4, 9)]
        self.assertAlmostEqual(plan.total(ranges), 8.0)


if __name__ == "__main__":
    unittest.main()
