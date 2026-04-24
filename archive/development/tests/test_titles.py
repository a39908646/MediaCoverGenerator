from __future__ import annotations

import unittest

from mediacovergenerator.titles import TitleConfigResolver


class TitleConfigResolverTest(unittest.TestCase):
    def test_resolve_exact_match_and_bg_color(self) -> None:
        resolver = TitleConfigResolver(
            "\"电视剧\": [\"剧集\", \"SERIES\", \"#112233\"]\n"
            "\"电影\": [\"电影\", \"MOVIES\"]\n"
        )

        resolved = resolver.resolve("电视剧")

        self.assertEqual(resolved.zh_title, "剧集")
        self.assertEqual(resolved.en_title, "SERIES")
        self.assertEqual(resolved.bg_color, "#112233")

    def test_resolve_quoted_numeric_like_key(self) -> None:
        resolver = TitleConfigResolver("2024合集: [\"年度合集\", \"YEAR IN REVIEW\"]")

        resolved = resolver.resolve("2024合集")

        self.assertEqual(resolved.zh_title, "年度合集")
        self.assertEqual(resolved.en_title, "YEAR IN REVIEW")


if __name__ == "__main__":
    unittest.main()
