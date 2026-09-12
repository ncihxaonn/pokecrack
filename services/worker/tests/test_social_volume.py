from __future__ import annotations

import json

from pokecrack_worker.global_volume import SCHEMA_VERSION
from pokecrack_worker.social_volume import (
    BLUESKY_CANDIDATES_SQL,
    SOCIAL_SOURCE_QUERY_LIMIT,
    YOUTUBE_DISCOVERIES_SQL,
    build_manifest,
    extract_pack_count,
    sync_social_volume,
)


def test_extract_pack_count_prefers_the_number_adjacent_to_pack_unit() -> None:
    assert extract_pack_count("Pokémon TCG opening: 100 BOOSTERS, 5 hits") == 100
    assert extract_pack_count("宝可梦卡牌 100包开箱") == 100
    assert extract_pack_count("포켓몬 카드 20팩 개봉") == 20
    assert extract_pack_count("โปเกมอน เปิด 12 ซอง") == 12
    assert extract_pack_count("بوكيمون فتح 15 باك") == 15
    assert extract_pack_count("पोकेमोन कार्ड 18 पैक") == 18
    assert extract_pack_count("Pokemon TCG opening 1.5 packs") is None
    assert extract_pack_count("Pokemon TCG opening 100 boxes") is None
    assert extract_pack_count("100 packs opened") is None


class Executor:
    def __init__(self) -> None:
        self.imported: dict[str, object] | None = None

    def query(self, sql: str, params: dict[str, object]) -> list[dict[str, object]]:
        assert params == {} or set(params) == {"manifest"}
        if sql == YOUTUBE_DISCOVERIES_SQL:
            return [
                {
                    "source_url": "https://www.youtube.com/watch?v=AbCdEfGhI_1",
                    "title": "Pokémon TCG opening 100 BOOSTERS",
                },
                {
                    "source_url": "https://www.youtube.com/watch?v=ZzYyXxWwVv0",
                    "title": "Pokemon TCG opening 100 boxes",
                },
            ]
        if sql == BLUESKY_CANDIDATES_SQL:
            return [
                {
                    "public_url": "https://bsky.app/profile/did:plc:abc/post/pack100",
                    "text_excerpt": "宝可梦卡牌 25包开箱",
                }
            ]
        assert "import_global_volume_intake_v1" in sql
        self.imported = json.loads(str(params["manifest"]))
        return [
            {
                "result": {
                    "status": "accepted",
                    "snapshot_sha256": self.imported["snapshot_sha256"],
                    "candidates_received": len(self.imported["candidates"]),
                    "candidates_inserted": len(self.imported["candidates"]),
                    "conflicting_count": 0,
                }
            }
        ]


def test_social_manifest_is_bounded_and_does_not_persist_claim_text() -> None:
    executor = Executor()
    manifest = build_manifest(executor)
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert [item["pack_count"] for item in manifest["candidates"]] == [25, 100]
    assert manifest["candidates"][1]["url"] == "https://www.youtube.com/embed/AbCdEfGhI_1"
    assert all(item["pack_precision"] == "title_claim" for item in manifest["candidates"])
    serialized = json.dumps(manifest)
    assert "100 BOOSTERS" not in serialized
    assert "25包开箱" not in serialized
    assert "text_excerpt" not in serialized
    assert f"LIMIT {SOCIAL_SOURCE_QUERY_LIMIT}" in YOUTUBE_DISCOVERIES_SQL
    assert f"LIMIT {SOCIAL_SOURCE_QUERY_LIMIT}" in BLUESKY_CANDIDATES_SQL


def test_social_sync_imports_only_typed_quantity_candidates() -> None:
    executor = Executor()
    result = sync_social_volume(executor)
    assert result["metadata_candidates"] == 2
    assert result["candidates_received"] == 2
    assert executor.imported is not None
