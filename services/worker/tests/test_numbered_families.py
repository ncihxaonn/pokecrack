"""Worker orchestration with synthetic HTTP and fenced database responses."""

import json
from dataclasses import replace

import pytest
from test_hatena_numbered import NOW, URL, page

from pokecrack_worker import numbered_families as family
from pokecrack_worker.collectors.base import FetchResponse
from pokecrack_worker.jobs.models import CompletionEffect, Job
from pokecrack_worker.runtime import JobDeferred


class DB:
    def __init__(self, target=URL, denied=None):
        self.rows = [{"target_url": target}]
        self.denied = denied
        self.authorizations = 0
        self.calls = []
        self.staged = None
        self.deferred_until = None

    def query(self, sql, params):
        self.calls.append((sql, dict(params)))
        if "begin_numbered_family" in sql:
            return self.rows
        if "authorize_numbered_family" in sql:
            self.authorizations += 1
            return [{"allowed": self.authorizations != self.denied}]
        if "defer_numbered_family" in sql:
            self.deferred_until = params["until"]
            return [{"deferred": True}]
        assert "stage_numbered_family" in sql
        self.staged = json.loads(params["result"])
        return []


class HTTP:
    def __init__(self, body=None, robots="User-agent: *\nAllow: /", status=200):
        self.body = page() if body is None else body
        self.robots = robots
        self.status = status
        self.calls = []

    def get(self, url, *, timeout_seconds):
        self.calls.append(url)
        body = self.robots if url == family.ROBOTS_URL else self.body
        return FetchResponse(self.status, url, {}, body.encode())


JOB = Job(
    "synthetic", family.JOB_TYPE, {"family": family.FAMILY}, lease_generation=7, is_demo=False
)


def run(db, http, *, job=JOB):
    sleeps = []
    result = family.make_handler(db, http, "worker", sleeper=sleeps.append, clock=lambda: NOW)(job)
    return result, sleeps


def test_article_reaches_minimal_staging_with_fencing():
    db, http = DB(), HTTP()
    result, sleeps = run(db, http)
    assert result is CompletionEffect.FINALIZE_NUMBERED_FAMILY
    assert sleeps == [30]
    assert http.calls == [family.ROBOTS_URL, URL]
    evidence = db.staged["evidence"]
    assert evidence["pack_count"] == 10
    assert len(set(evidence["resource_sha256s"])) == 10
    assert evidence["opening_country"] is None and evidence["opened_at"] is None
    assert evidence["statistics_eligible"] is False
    assert all(params["generation"] == 7 and params["worker"] == "worker" for _, params in db.calls)
    assert not any("finalize" in sql for sql, _ in db.calls)


def test_feed_reaches_count_free_staging():
    db = DB(family.FEED_URL)
    http = HTTP(
        f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><link href="{URL}" /></entry></feed>'
    )
    run(db, http)
    assert db.staged == {"urls": [URL]}


@pytest.mark.parametrize("denied", [1, 2])
def test_reauthorization_denial_stops_before_http(denied):
    db, http = DB(denied=denied), HTTP()
    with pytest.raises(JobDeferred):
        run(db, http)
    assert len(http.calls) == denied - 1
    assert db.staged is None


def test_robots_denial_does_not_fetch_article():
    db, http = DB(), HTTP(robots="User-agent: *\nDisallow: /")
    _, sleeps = run(db, http)
    assert http.calls == [family.ROBOTS_URL] and sleeps == []
    assert db.staged == {"quarantine": True}


@pytest.mark.parametrize("body", ["bad article containing personal content", "x" * 1_000_001])
def test_bad_input_never_persists_raw_content(body):
    db, http = DB(), HTTP(body)
    run(db, http)
    assert db.staged == {"quarantine": True}


def test_bad_status_does_not_fetch_article():
    db, http = DB(), HTTP(status=403)
    run(db, http)
    assert http.calls == [family.ROBOTS_URL]
    assert db.staged == {"quarantine": True}


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_transient_status_defers_without_quarantine(status):
    db, http = DB(), HTTP(status=status)
    with pytest.raises(JobDeferred):
        run(db, http)
    assert db.staged is None


def test_transport_failure_is_not_bad_source_evidence():
    class Unavailable(HTTP):
        def get(self, url, *, timeout_seconds):
            raise TimeoutError("upstream detail must not be staged")

    db = DB()
    with pytest.raises(JobDeferred):
        run(db, Unavailable())
    assert db.staged is None


@pytest.mark.parametrize("value", ["7200", "Fri, 11 Sep 2026 00:00:00 GMT"])
def test_server_retry_after_is_respected(value):
    from datetime import timedelta

    class Busy(HTTP):
        def get(self, url, *, timeout_seconds):
            return FetchResponse(429, url, {"Retry-After": value}, b"")

    db = DB()
    with pytest.raises(JobDeferred) as raised:
        run(db, Busy())
    assert raised.value.retry_at >= NOW + timedelta(hours=2)
    assert db.deferred_until == raised.value.retry_at.isoformat()
    assert db.staged is None


def test_paused_family_defers_without_fetch_or_stage():
    db, http = DB(), HTTP()
    db.rows = []
    with pytest.raises(JobDeferred):
        run(db, http)
    assert http.calls == [] and db.staged is None


@pytest.mark.parametrize(
    "rows",
    [
        [{"target_url": "https://other.example/"}],
        [{"target_url": 5}],
        [{}, {}],
        [{"target_url": URL + "?redirect=elsewhere"}],
    ],
)
def test_bad_acquisition_has_no_network_access(rows):
    db, http = DB(), HTTP()
    db.rows = rows
    with pytest.raises(ValueError):
        run(db, http)
    assert http.calls == [] and db.staged is None


@pytest.mark.parametrize(
    "job",
    [
        replace(JOB, payload={"family": "pokesup-enumerated"}),
        replace(JOB, is_demo=True),
        Job("unknown-provenance", family.JOB_TYPE, {"family": family.FAMILY}),
    ],
)
def test_other_family_demo_or_unknown_provenance_cannot_call_rpcs(job):
    db, http = DB(), HTTP()
    with pytest.raises(ValueError):
        run(db, http, job=job)
    assert db.calls == [] and http.calls == []


@pytest.mark.parametrize("value", [None, True, "false", 0])
def test_database_job_requires_literal_false_provenance(value):
    from test_live_composition import _job_row

    from pokecrack_worker.jobs.postgres import job_from_row

    row = _job_row(status="pending", locked=False)
    row["is_demo"] = value
    assert job_from_row(row).is_demo
    row["is_demo"] = False
    assert not job_from_row(row).is_demo
    del row["is_demo"]
    assert job_from_row(row).is_demo
