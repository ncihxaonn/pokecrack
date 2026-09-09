"""Bounded source-family discovery. Approval is reviewed code, never worker input.

PokeSup M2/M3 numbered cohorts passed source review and real parser probes.
Runtime opt-in and the owner-controlled database switch remain separate gates.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree

from pokecrack_worker.collectors.base import PUBLIC_COLLECTOR_USER_AGENT, HTTPClient
from pokecrack_worker.jobs.models import CompletionEffect, Job
from pokecrack_worker.jobs.postgres import QueryExecutor

JOB_TYPE = "source.family.cycle"
VERSION = "pokesup-enumerated-v1"
FAMILY = "pokesup-enumerated"
ROOT = "https://pokesup.com"
SITEMAP = ROOT + "/blog-sitemap.xml"
EXCLUDED = ROOT + "/blog/unboxing-m5/"
URL_PATTERN = re.compile(
    r"https://pokesup\.com/blog/unboxing-([a-z][a-z0-9]{0,15})(?:-([2-9]|[1-9][0-9]))?/"
)
LABELS = tuple(f"{side}{number}パック" for side in ("左", "右") for number in range(1, 16))


@dataclass(frozen=True)
class FamilyPolicy:
    key: str = FAMILY
    version: str = VERSION
    approved: bool = True
    # Reviewed identities; every event must still pass deterministic admission.
    products: tuple[tuple[str, str], ...] = (("m2", "インフェルノX"), ("m3", "ムニキスゼロ"))


POLICY = FamilyPolicy()


def discover(document: str) -> tuple[str, ...]:
    """Enumerate only canonical opening URLs; never traverse arbitrary links."""
    if len(document.encode()) > 1_000_000 or "<!" in document:
        # Sitemap comments are benign, but DTD/entities are not accepted.
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", document, re.I):
            raise ValueError("sitemap_dtd")
        if len(document.encode()) > 1_000_000:
            raise ValueError("sitemap_size")
    root = ElementTree.fromstring(document)
    urls = tuple(
        sorted(
            {
                node.text
                for node in root.iter()
                if node.tag == "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
                and node.text
                and URL_PATTERN.fullmatch(node.text)
            }
        )
    )
    if len(urls) > 200:
        raise ValueError("sitemap_limit")
    return urls


class OpeningHTML(HTMLParser):
    """Extract minimal structural facts; comments/scripts cannot supply labels."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.canonical: list[str] = []
        self.headings: list[str] = []
        self.labels: list[str] = []
        self.images: list[str] = []
        self.videos: list[str] = []
        self._capture: str | None = None
        self._text = ""
        self._section = False
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag in {"script", "style", "template", "noscript"}:
            self._ignored += 1
        if self._ignored:
            return
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical.append(a.get("href") or "")
        if tag == "h2":
            self._capture, self._text, self._section = "h2", "", False
        if tag == "div" and a.get("class") == "_caption" and self._section:
            self._capture, self._text = "div", ""
        if tag == "img" and self._section:
            self.images.append(a.get("src") or "")
        if tag == "iframe":
            self.videos.append(a.get("src") or "")

    def handle_data(self, data: str) -> None:
        if self._capture and not self._ignored:
            self._text += data

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template", "noscript"} and self._ignored:
            self._ignored -= 1
        if self._ignored or tag != self._capture:
            return
        text = self._text.strip()
        if tag == "h2":
            self.headings.append(text)
            self._section = bool(re.fullmatch(r".+開封（[1-9][0-9]?箱目）", text))
        else:
            self.labels.append(text)
        self._capture = None


def verify(url: str, document: str, metadata: object, *, now: datetime) -> dict[str, object]:
    """Return only factual identifiers and enumeration; SQL determines admission."""
    match = URL_PATTERN.fullmatch(url)
    if match is None or match[1] == "m5":
        raise ValueError("scope_or_fixed_duplicate")
    products = dict(POLICY.products)
    product = match[1]
    ordinal = int(match[2] or "1")
    slug = url.rstrip("/").rsplit("/", 1)[1]
    if product not in products:
        raise ValueError("pending_product_review")
    if not isinstance(metadata, list) or len(metadata) != 1 or not isinstance(metadata[0], dict):
        raise ValueError("metadata_identity")
    meta = metadata[0]
    if (
        set(meta) != {"id", "slug", "link", "date_gmt"}
        or meta["link"] != url
        or meta["slug"] != slug
    ):
        raise ValueError("metadata_identity")
    if type(meta["id"]) is not int or meta["id"] <= 0:
        raise ValueError("metadata_identity")
    date = meta["date_gmt"]
    if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", date):
        raise ValueError("publication_date")
    published = datetime.fromisoformat(date).replace(tzinfo=UTC)
    if not now - timedelta(days=365) < published <= now:
        raise ValueError("outside_window")
    parsed = OpeningHTML()
    parsed.feed(document)
    if (
        parsed.canonical != [url]
        or parsed.headings.count(products[product] + f"開封（{ordinal}箱目）") != 1
    ):
        raise ValueError("opening_identity")
    if tuple(parsed.labels) != LABELS:
        raise ValueError("pack_enumeration")
    expected_images = [
        f"/assets/img/blog/{slug}/pack_{side}_{n:02}.jpg"
        for side in ("l", "r")
        for n in range(1, 16)
    ]
    unpadded_images = [
        f"/assets/img/blog/{slug}/pack_{side}_{n}.jpg" for side in ("l", "r") for n in range(1, 16)
    ]
    if parsed.images not in (expected_images, unpadded_images):
        raise ValueError("pack_resource_identity")
    # Resource identifiers are hashed, never fetched or persisted. A unique
    # resource hash is NOT by itself proof of independent physical packs.
    resource_hash = hashlib.sha256("\n".join(parsed.images).encode()).hexdigest()
    if len(parsed.videos) > 1:
        raise ValueError("ambiguous_video_identity")
    video_hashes = []
    for video in parsed.videos:
        parts = urlsplit(video)
        match_video = re.fullmatch(r"/embed/([A-Za-z0-9_-]{11})", parts.path)
        if (
            parts.scheme != "https"
            or parts.netloc != "www.youtube.com"
            or match_video is None
            or parts.fragment
        ):
            raise ValueError("unsupported_video_identity")
        video_hashes.append(hashlib.sha256(("youtube:" + match_video[1]).encode()).hexdigest())
    return {
        "url": url,
        "post_id": meta["id"],
        "published_at": published.isoformat(),
        "product": product,
        "opening_ordinal": ordinal,
        "labels": list(LABELS),
        "resource_sha256": resource_hash,
        "resource_sha256s": [hashlib.sha256(path.encode()).hexdigest() for path in parsed.images],
        "video_sha256s": video_hashes,
    }


def make_handler(
    executor: QueryExecutor,
    client: HTTPClient,
    worker_id: str,
    *,
    sleeper: Callable[[float], None] = time.sleep,
) -> Callable[[Job], CompletionEffect]:
    def cycle(job: Job) -> CompletionEffect:
        if not POLICY.approved or job.kind != JOB_TYPE or job.payload != {"family": FAMILY}:
            raise ValueError("family_not_approved")
        params: dict[str, object] = {
            "job": job.id,
            "worker": worker_id,
            "generation": job.lease_generation,
        }
        rows = executor.query(
            "select * from ingest.begin_source_family_v1(%(job)s::uuid, %(worker)s, %(generation)s)",
            params,
        )
        if len(rows) != 1:
            raise ValueError("family_lease_or_gate")
        target = str(rows[0]["target_url"])

        def fetch(url: str) -> str:
            if urlsplit(url).netloc != "pokesup.com":
                raise ValueError("family_host")
            authorization = executor.query(
                "select ingest.authorize_source_family_request_v1(%(job)s::uuid, %(worker)s, %(generation)s, %(url)s) as allowed",
                {**params, "url": url},
            )
            if len(authorization) != 1 or authorization[0].get("allowed") is not True:
                raise ValueError("family_access_revoked")
            # Composition supplies ScraplingHTTPClient.live(): its pinned static
            # backend disables redirects before I/O and aborts the streaming
            # callback above 1 MB. These DTO checks are defense in depth, not
            # the acquisition cap (see collectors/scrapling/backend.py).
            response = client.get(url, timeout_seconds=20)
            if response.status_code != 200 or response.url != url or len(response.body) > 1_000_000:
                raise ValueError("access_failed")
            return response.body.decode("utf-8", errors="strict")

        result: dict[str, object]
        try:
            robots = RobotFileParser()
            robots.parse(fetch(ROOT + "/robots.txt").splitlines())
            urls = [target]
            if target != SITEMAP:
                if not URL_PATTERN.fullmatch(target):
                    raise ValueError("scope")
                slug = target.rstrip("/").rsplit("/", 1)[1]
                urls.append(
                    ROOT + "/wp-json/wp/v2/blog?slug=" + slug + "&_fields=id,slug,date_gmt,link"
                )
            for url in urls:
                if not robots.can_fetch(PUBLIC_COLLECTOR_USER_AGENT, url):
                    raise ValueError("robots_denied")
            sleeper(30)
            body = fetch(target)
            if target == SITEMAP:
                result = {"urls": list(discover(body))}
            else:
                sleeper(30)
                metadata = json.loads(fetch(urls[1]))
                result = {"evidence": verify(target, body, metadata, now=datetime.now(UTC))}
        except Exception:
            # Do not persist exception strings, pages, response headers or media.
            result = {"quarantine": True}
        params["result"] = json.dumps(result)
        executor.query(
            "select ingest.stage_source_family_v1(%(job)s::uuid, %(worker)s, %(generation)s, %(result)s::jsonb)",
            params,
        )
        return CompletionEffect.FINALIZE_SOURCE_FAMILY

    return cycle
