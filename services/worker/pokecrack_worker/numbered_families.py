"""Fenced worker cycle for publisher-level numbered-opening discovery.

The corresponding database RPCs own candidate selection, permanent deduplication
and admission. This module is not enabled by composition until that migration,
its restore contract and release checks are installed together.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.robotparser import RobotFileParser

from pokecrack_worker.collectors.base import PUBLIC_COLLECTOR_USER_AGENT, CollectorError, HTTPClient
from pokecrack_worker.collectors.scrapling.adapters.hatena_discovery import (
    ARTICLE,
    FEED_URL,
    discover_numbered_candidates,
)
from pokecrack_worker.collectors.scrapling.adapters.hatena_numbered import parse_numbered_opening
from pokecrack_worker.jobs.models import CompletionEffect, Job
from pokecrack_worker.jobs.postgres import QueryExecutor
from pokecrack_worker.runtime import JobDeferred

JOB_TYPE = "source.family.cycle"
FAMILY = "kozaru-numbered"
VERSION = "kozaru-numbered-v1"
ROBOTS_URL = "https://www.kozaru02.com/robots.txt"
PRODUCT = "MEGAドリームex"
PACK_COUNT = 10


def make_handler(
    executor: QueryExecutor,
    client: HTTPClient,
    worker_id: str,
    *,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Callable[[Job], CompletionEffect]:
    """Acquire → robots → feed/article → minimal staging; no direct admission.

    Every HTTP request needs a fresh fenced database authorization. The live
    client must disable redirects and enforce the 1 MB streaming response bound.
    """

    def cycle(job: Job) -> CompletionEffect:
        if job.kind != JOB_TYPE or job.payload != {"family": FAMILY} or job.is_demo:
            raise ValueError("numbered_family_scope")
        params: dict[str, object] = {
            "job": job.id,
            "worker": worker_id,
            "generation": job.lease_generation,
        }
        rows = executor.query(
            "select * from ingest.begin_numbered_family_v1(%(job)s::uuid, %(worker)s, %(generation)s)",
            params,
        )
        if not rows:
            raise JobDeferred(
                retry_at=clock() + timedelta(minutes=5),
                code="numbered_family_acquisition_deferred",
            )
        if len(rows) != 1:
            raise ValueError("numbered_family_acquisition_shape")
        target = rows[0].get("target_url")
        if not isinstance(target, str) or not (target == FEED_URL or ARTICLE.fullmatch(target)):
            raise ValueError("numbered_family_target_scope")

        def fetch(url: str) -> str:
            # The acquired target is immutable for this invocation. Even a
            # malformed DB response cannot turn this worker into a URL proxy.
            if url not in {ROBOTS_URL, target}:
                raise ValueError("numbered_family_request_scope")
            allowed = executor.query(
                "select ingest.authorize_numbered_family_request_v1(%(job)s::uuid, %(worker)s, %(generation)s, %(url)s) as allowed",
                {**params, "url": url},
            )
            if len(allowed) != 1 or allowed[0].get("allowed") is not True:
                raise JobDeferred(
                    retry_at=clock() + timedelta(minutes=5),
                    code="numbered_family_access_deferred",
                )
            try:
                response = client.get(url, timeout_seconds=20)
            except Exception as error:
                raise JobDeferred(
                    retry_at=clock() + timedelta(minutes=5),
                    code="numbered_family_transport_deferred",
                ) from error
            if response.status_code == 429 or response.status_code >= 500:
                retry_at = clock() + timedelta(hours=1)
                value = next(
                    (v for k, v in response.headers.items() if k.lower() == "retry-after"), ""
                )
                try:
                    if value.isdecimal():
                        retry_at = max(retry_at, clock() + timedelta(seconds=int(value)))
                    elif value:
                        date = parsedate_to_datetime(value)
                        if date.utcoffset() is not None:
                            retry_at = max(retry_at, date)
                except OverflowError:
                    # Never shorten an explicitly very long requested pause.
                    retry_at = datetime.max.replace(tzinfo=UTC)
                except (TypeError, ValueError):
                    pass
                raise JobDeferred(retry_at=retry_at, code="numbered_family_server_deferred")
            if response.status_code != 200 or response.url != url or len(response.body) > 1_000_000:
                raise CollectorError("numbered_family_access_failed")
            try:
                return response.body.decode("utf-8", errors="strict")
            except UnicodeError as error:
                raise JobDeferred(
                    retry_at=clock() + timedelta(minutes=5),
                    code="numbered_family_encoding_deferred",
                ) from error

        result: dict[str, object]
        try:
            robots = RobotFileParser()
            robots.parse(fetch(ROBOTS_URL).splitlines())
            if not robots.can_fetch(PUBLIC_COLLECTOR_USER_AGENT, target):
                raise CollectorError("numbered_family_robots_denied")
            sleeper(30)
            body = fetch(target)
            if target == FEED_URL:
                result = {"urls": list(discover_numbered_candidates(body))}
            else:
                candidate = parse_numbered_opening(
                    body,
                    expected_url=target,
                    product_label=PRODUCT,
                    expected_pack_count=PACK_COUNT,
                    now=clock(),
                )
                result = {"evidence": asdict(candidate)}
        except CollectorError:
            # No publisher body, personal details, HTTP headers or exception
            # strings enter durable staging. A bad article cannot poison others.
            result = {"quarantine": True}
        executor.query(
            "select ingest.stage_numbered_family_v1(%(job)s::uuid, %(worker)s, %(generation)s, %(result)s::jsonb)",
            {**params, "result": json.dumps(result)},
        )
        return CompletionEffect.FINALIZE_NUMBERED_FAMILY

    return cycle
