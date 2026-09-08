from __future__ import annotations

import unittest

from pokecrack_worker.collectors.base import CollectorError
from pokecrack_worker.collectors.scrapling.adapters.nanjakorya_study import (
    EXPECTED_GROUPS,
    PUBLISHED_AT,
    RARITIES,
    parse_star_birth_report,
)


def document() -> str:
    # Synthetic structure containing only short identifiers and factual counts.
    result = f'<meta property="article:published_time" content="{PUBLISHED_AT}">'
    result += "<article><h1>バラ100パック開けてみた結果【ポケカ-スターバース編】</h1>"
    for first, last, counts in EXPECTED_GROUPS:
        suffix = "（プレミアムボックス）" if (first, last) == (31, 50) else ""
        result += f"<h3>{first}〜{last}パック目{suffix}</h3><p>（"
        result += "、".join(f"{key}：{count}枚" for key, count in zip(RARITIES, counts, strict=True) if count)
        result += "）</p>"
    return result + "<h2>summary</h2></article>"


class NanjakoryaStudyTests(unittest.TestCase):
    def test_exact_complete_report_without_inferred_location_or_probability(self) -> None:
        result = parse_star_birth_report(document())
        self.assertEqual(result.pack_count, 100)
        self.assertEqual(result.rarity_card_counts, (16, 6, 4, 1))
        self.assertIsNone(result.opening_country)
        self.assertIsNone(result.opened_at)
        self.assertFalse(result.statistics_eligible)
        self.assertEqual(len(result.evidence_sha256), 64)

    def test_changed_evidence_fails_closed(self) -> None:
        for old, new in [
            ("RR：2枚", "RR：3枚"),
            ("91〜100パック目", "91〜110パック目"),
            ("31〜50パック目", "31〜40パック目"),
            ("SR：1枚", "SR：1枚、SR：1枚"),
            (PUBLISHED_AT, "2022-06-03T20:00:22+09:00"),
            ("スターバース編", "別の商品"),
            ("31〜50パック目（プレミアムボックス）", "31〜50パック目"),
            ("1〜10パック目", "1〜10パック目（プレミアムボックス）"),
        ]:
            with self.subTest(old=old), self.assertRaises(CollectorError):
                parse_star_birth_report(document().replace(old, new, 1))

    def test_hidden_counts_cannot_supply_missing_segment(self) -> None:
        text = document().replace("<p>（RR：2枚、SR：1枚）</p>",
                                  "<script><p>（RR：2枚、SR：1枚）</p></script>", 1)
        with self.assertRaises(CollectorError):
            parse_star_birth_report(text)

    def test_duplicate_and_out_of_article_evidence_rejected(self) -> None:
        for text in [document() + document(),
                     document().replace("<article>", "<div>").replace("</article>", "</div>")]:
            with self.assertRaises(CollectorError):
                parse_star_birth_report(text)

    def test_inline_formatting_does_not_change_minimal_fact_hash(self) -> None:
        self.assertEqual(parse_star_birth_report(document()), parse_star_birth_report(
            document().replace("RR：2枚", "<b>RR</b>：2枚", 1)))

    def test_mismatched_hidden_end_tag_cannot_expose_evidence(self) -> None:
        hidden = document().replace("<article>", "<article><template></script>")
        hidden = hidden.replace("</article>", "</template></article>")
        with self.assertRaises(CollectorError):
            parse_star_birth_report(hidden)
