"""A publishing kit the creator actually pastes in — not a wall of tags."""
import unittest

from shortsforge import pack


def cues(*texts):
    return [{"start": i, "end": i + 1, "text": t} for i, t in enumerate(texts)]


class TestTitles(unittest.TestCase):
    def test_joins_short_phrases_into_a_headline(self):
        got = pack.titles(cues("sword fight", "on the mountain"))
        self.assertEqual(got[0], "sword fight, on the mountain")

    def test_uses_a_chinese_comma_for_chinese_material(self):
        got = pack.titles(cues("十五年的战争", "投入了六十五万人"))
        self.assertIn("，", got[0])

    def test_respects_max_len(self):
        got = pack.titles(cues("x" * 20, "y" * 20, "z" * 20), max_len=30)
        self.assertTrue(all(len(t) <= 30 for t in got))

    def test_skips_filler_units(self):
        got = pack.titles(cues("嗯", "嗯", "嗯"))
        self.assertEqual(got, [])

    def test_no_captions_means_no_titles(self):
        self.assertEqual(pack.titles([]), [])


class TestHashtags(unittest.TestCase):
    def test_most_frequent_word_comes_first(self):
        tags = pack.hashtags(cues("sword fight sword mountain sword"))
        self.assertEqual(tags[0], "#sword")

    def test_drops_words_that_are_substrings_of_a_picked_tag(self):
        tags = pack.hashtags(cues("sword swordfish swordfish"))
        self.assertIn("#swordfish", tags)
        self.assertNotIn("#sword", tags)

    def test_no_captions_means_no_tags(self):
        self.assertEqual(pack.hashtags([]), [])

    def test_limit_is_respected(self):
        text = " ".join("word%d word%d" % (i, i) for i in range(20))
        self.assertLessEqual(len(pack.hashtags(cues(text), limit=4)), 4)


if __name__ == "__main__":
    unittest.main()
