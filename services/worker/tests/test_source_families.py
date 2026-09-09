"""Synthetic layouts exercise gates; fixtures are not real source evidence."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from pokecrack_worker import source_families
from pokecrack_worker.collectors.base import FetchResponse
from pokecrack_worker.composition import (
    build_live_worker_runtime,
    live_schedule_entries,
    require_worker_job_types,
)
from pokecrack_worker.config.settings import Settings
from pokecrack_worker.jobs.models import CompletionEffect, Job
from pokecrack_worker.source_families import (
    EXCLUDED,
    LABELS,
    POLICY,
    ROOT,
    discover,
    verify,
)

NOW = datetime(2026, 9, 9, tzinfo=UTC)
URL = ROOT + "/blog/unboxing-m2/"


def fixture() -> tuple[str, list[dict[str, object]]]:
    body = f'<link rel="canonical" href="{URL}"><h2>インフェルノX開封（1箱目）</h2>'
    for side, letter in (("左", "l"), ("右", "r")):
        for n in range(1, 16):
            body += f'<img src="/assets/img/blog/unboxing-m2/pack_{letter}_{n:02}.jpg"><div class="_caption">{side}{n}パック</div>'
    body += "<h2>封入率</h2>"
    return body, [
        {"id": 462, "slug": "unboxing-m2", "link": URL, "date_gmt": "2025-09-30T10:44:54"}
    ]


def test_source_review_does_not_enable_runtime_collection() -> None:
    assert POLICY.approved
    assert not Settings(_env_file=None).source_family_collection_enabled


def test_paused_family_schedule_does_not_block_other_jobs() -> None:
    from test_live_composition import RecordingExecutor, _job_row

    from pokecrack_worker.jobs.postgres import PostgresJobRepository
    from pokecrack_worker.scheduler import ScheduleEntry, Scheduler

    executor = RecordingExecutor([[], [_job_row(status="pending", locked=False)]])
    result = Scheduler(
        PostgresJobRepository(executor),
        [
            ScheduleEntry(
                name="family",
                job_type=source_families.JOB_TYPE,
                interval=timedelta(hours=1),
                payload={"family": "pokesup-enumerated"},
            ),
            ScheduleEntry(
                name="cleanup", job_type="maintenance.cleanup", interval=timedelta(hours=1)
            ),
        ],
    ).run_due(now=NOW)
    assert result.planned == 2
    assert result.created == 1
    assert result.due_names == ("family", "cleanup")
    assert "enqueue_source_family_v1" in executor.calls[0][0]
    assert "enqueue_scheduled_job_v1" in executor.calls[1][0]


def test_exact_enumeration_only() -> None:
    body, meta = fixture()
    result = verify(URL, body, meta, now=NOW)
    assert result["labels"] == list(LABELS)
    assert set(result) == {
        "url",
        "post_id",
        "published_at",
        "product",
        "opening_ordinal",
        "labels",
        "resource_sha256",
        "resource_sha256s",
        "video_sha256s",
    }
    assert "pack_count" not in result


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.replace("左1パック", "左2パック"),
        lambda s: s.replace("右15パック", ""),
        lambda s: s.replace("左1パック", "1箱"),
        lambda s: s.replace("pack_l_01.jpg", "pack_l_02.jpg"),
        lambda s: s.replace("unboxing-m2/pack_", "unboxing-m5/pack_"),
        lambda s: s.replace("（1箱目）", "（2箱目）"),
        lambda s: s.replace('href="' + URL, 'href="https://other.example/'),
        lambda s: "<!--" + s + "-->",
        lambda s: "<script>" + s + "</script>",
    ],
)
def test_ambiguous_layout_rejected(change) -> None:  # type: ignore[no-untyped-def]
    body, meta = fixture()
    with pytest.raises(ValueError):
        verify(URL, change(body), meta, now=NOW)


@pytest.mark.parametrize(
    "url",
    [
        EXCLUDED,
        URL + "?alias=1",
        URL + "#section",
        ROOT + "/blog/unboxing-m2-2/",
        "https://evil.example/a/",
    ],
)
def test_scope_and_fixed_duplicate(url: str) -> None:
    body, meta = fixture()
    with pytest.raises(ValueError):
        verify(url, body, meta, now=NOW)


@pytest.mark.parametrize("date", [NOW + timedelta(seconds=1), NOW - timedelta(days=365)])
def test_strict_window(date: datetime) -> None:
    body, meta = fixture()
    meta[0]["date_gmt"] = date.replace(tzinfo=None).isoformat()
    with pytest.raises(ValueError, match="outside_window"):
        verify(URL, body, meta, now=NOW)


def test_comments_do_not_define_cohort_or_packs() -> None:
    body, meta = fixture()
    assert verify(URL, body + '<!--<div class="_caption">左1パック</div>-->', meta, now=NOW)


def test_active_video_identity_is_normalized_and_comments_ignored() -> None:
    body, meta = fixture()
    comment = '<!--<iframe src="https://www.youtube.com/embed/XXXXXXXXXXX"></iframe>-->'
    first = verify(
        URL,
        body + comment + '<iframe src="https://www.youtube.com/embed/dga5O7ytsgA?si=one"></iframe>',
        meta,
        now=NOW,
    )
    second = verify(
        URL,
        body + '<iframe src="https://www.youtube.com/embed/dga5O7ytsgA?si=two"></iframe>',
        meta,
        now=NOW,
    )
    assert first["video_sha256s"] == second["video_sha256s"]
    assert len(first["video_sha256s"]) == 1  # type: ignore[arg-type]
    assert len(first["labels"]) == 30  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="ambiguous_video_identity"):
        verify(
            URL,
            body + '<iframe src="https://www.youtube.com/embed/dga5O7ytsgA"></iframe>' * 2,
            meta,
            now=NOW,
        )


def test_distinct_ordinal_requires_matching_page_section_and_resources() -> None:
    body, meta = fixture()
    second = URL.replace("m2/", "m2-2/")
    body = body.replace("m2/", "m2-2/").replace("（1箱目）", "（2箱目）")
    meta[0].update(id=999, slug="unboxing-m2-2", link=second)
    assert verify(second, body, meta, now=NOW)["opening_ordinal"] == 2


def test_sitemap_discovery_retains_fixed_url_for_duplicate_ledger() -> None:
    xml = (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(
            f"<url><loc>{u}</loc></url>" for u in [URL, EXCLUDED, URL, "https://evil.example/a/"]
        )
        + "</urlset>"
    )
    assert discover(xml) == (URL, EXCLUDED)


def test_sitemap_entities_rejected() -> None:
    with pytest.raises(ValueError, match="sitemap_dtd"):
        discover("<!DOCTYPE x><urlset/>")


@pytest.mark.parametrize("youtube_enabled", [False, True])
def test_enabled_schedule_and_handler_order(
    monkeypatch: pytest.MonkeyPatch, youtube_enabled: bool
) -> None:
    monkeypatch.setattr(source_families, "POLICY", replace(POLICY, approved=True))
    settings = Settings(
        _env_file=None,
        data_mode="live",
        worker_role="collector",
        supabase_db_url="postgresql://example.invalid/test",
        public_study_collection_enabled=True,
        source_family_collection_enabled=True,
        scrapling_enabled=True,
        youtube_collection_enabled=youtube_enabled,
        youtube_api_key="fixture-test-only" if youtube_enabled else None,
    )

    class DB:
        def query(self, sql, params):  # type: ignore[no-untyped-def]
            return []

    runtime = build_live_worker_runtime(settings, executor=DB())
    assert tuple(runtime.handlers) == require_worker_job_types(settings)
    schedules = live_schedule_entries(settings.model_copy(update={"worker_role": "scheduler"}))
    family = [entry for entry in schedules if entry.job_type == source_families.JOB_TYPE]
    assert len(family) == 1 and family[0].slot(NOW + timedelta(minutes=42)) == NOW


@pytest.mark.parametrize("denied_request", [None, 1, 2, 3])
def test_each_network_request_requires_database_authorization(
    monkeypatch: pytest.MonkeyPatch, denied_request: int | None
) -> None:
    monkeypatch.setattr(source_families, "POLICY", replace(POLICY, approved=True))
    body, meta = fixture()
    meta[0]["date_gmt"] = (
        (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0, tzinfo=None).isoformat()
    )

    class DB:
        count = 0
        result = None

        def query(self, sql, params):  # type: ignore[no-untyped-def]
            if "begin_source_family" in sql:
                return [{"target_url": URL}]
            if "authorize_source_family" in sql:
                self.count += 1
                return [{"allowed": self.count != denied_request}]
            self.result = json.loads(params["result"])
            return []

    class HTTP:
        calls = 0

        def get(self, url, *, timeout_seconds):  # type: ignore[no-untyped-def]
            self.calls += 1
            text = (
                "User-agent: *\nAllow: /\n"
                if url.endswith("robots.txt")
                else json.dumps(meta)
                if "wp-json" in url
                else body
            )
            return FetchResponse(200, url, {}, text.encode())

    db, http = DB(), HTTP()
    handler = source_families.make_handler(db, http, "worker", sleeper=lambda _: None)
    assert (
        handler(
            Job(
                "test",
                source_families.JOB_TYPE,
                {"family": source_families.FAMILY},
                lease_generation=1,
            )
        )
        == CompletionEffect.FINALIZE_SOURCE_FAMILY
    )
    assert http.calls == (3 if denied_request is None else denied_request - 1)
    assert db.result is not None
    assert ("evidence" in db.result) == (denied_request is None)
