from __future__ import annotations

import unittest

from pokecrack_worker.collectors.base import CollectorError
from pokecrack_worker.collectors.scrapling.adapters.paradigm_trigger_study import (
    EXPECTED_RARITIES,
    HEADERS,
    PUBLISHED_AT,
    PURCHASE_GROUPS,
    TITLE,
    parse_paradigm_trigger_report,
)


def document() -> str:
    # Synthetic markup; no retained article prose, card list or media.
    result = f'<meta property="article:published_time" content="{PUBLISHED_AT}">'
    result += f"<article><h1>{TITLE}</h1>"
    number = 0
    for label, rarities in zip(PURCHASE_GROUPS, EXPECTED_RARITIES, strict=True):
        result += f"<p>{label}</p><table><thead><tr>"
        result += "".join(f"<th>{header}</th>" for header in HEADERS)
        result += "</tr></thead><tbody>"
        for rarity in rarities.split():
            number += 1
            result += f"<tr><td>{number}</td><td>a</td><td>b</td><td>c</td>"
            result += f"<td>example({rarity})</td><td>d</td></tr>"
        result += "</tbody></table>"
    return result + "</article>"


class ParadigmTriggerStudyTests(unittest.TestCase):
    def test_complete_native_report_is_not_normalized_rate_evidence(self) -> None:
        report = parse_paradigm_trigger_report(document())
        self.assertEqual(report.pack_count, 100)
        self.assertEqual(report.rarity_card_counts, (14, 7, 1, 2))
        self.assertIsNone(report.opening_country)
        self.assertIsNone(report.opened_at)
        self.assertFalse(report.statistics_eligible)

    def test_changed_number_rarity_date_and_purchase_group_fail_closed(self) -> None:
        for old, new in [
            ("<td>100</td>", "<td>101</td>"),
            ("example(HR)", "example(SR)"),
            (PUBLISHED_AT, "2022-10-22T20:10:35+09:00"),
            (TITLE, "different product"),
            (PURCHASE_GROUPS[1], PURCHASE_GROUPS[0]),
            ("<td>a</td>", "<td></td>"),
            ("<th>4枚目</th>", "<th>5枚目</th>"),
        ]:
            with self.subTest(old=old), self.assertRaises(CollectorError):
                parse_paradigm_trigger_report(document().replace(old, new, 1))

    def test_hidden_duplicate_outside_and_incomplete_tables_rejected(self) -> None:
        for raw in [
            document() + document(),
            document().replace("<article>", "<div>").replace("</article>", "</div>"),
            document()
            .replace("<table>", "<template><table>", 1)
            .replace("</table>", "</table></template>", 1),
            document().replace("</table>", "", 1),
            document().replace("</article>", ""),
            document().replace("<td>a</td>", "<td><td>a</td></td>", 1),
        ]:
            with self.subTest(raw=raw[:100]), self.assertRaises(CollectorError):
                parse_paradigm_trigger_report(raw)

    def test_inline_formatting_and_fullwidth_header_preserve_digest(self) -> None:
        self.assertEqual(
            parse_paradigm_trigger_report(document()),
            parse_paradigm_trigger_report(
                document()
                .replace("example(RR)", "<b>example</b>(RR)")
                .replace("1枚目(C)", "１枚目(C)")
            ),
        )

    def test_related_article_cards_are_not_evidence(self) -> None:
        self.assertEqual(
            parse_paradigm_trigger_report(document()),
            parse_paradigm_trigger_report(document() + "<article><h2>Related</h2></article>"),
        )
        moved = document().replace("</h1>", "</h1></article><article>", 1)
        with self.assertRaises(CollectorError):
            parse_paradigm_trigger_report(moved)
