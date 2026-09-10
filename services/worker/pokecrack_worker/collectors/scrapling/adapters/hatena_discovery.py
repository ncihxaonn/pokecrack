"""Count-free discovery from the publisher's advertised Atom update feed.

No network access, arbitrary-host traversal, or automatic source approval. Feed
entries are candidates, never proof of an opening or its country.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree

from pokecrack_worker.collectors.base import CollectorError
from pokecrack_worker.collectors.scrapling.adapters.hatena_numbered import ROOT

FEED_URL = "https://www.kozaru02.com/feed"
ATOM = "{http://www.w3.org/2005/Atom}"
ARTICLE = re.compile(re.escape(ROOT) + r"[a-z0-9-]{1,120}")


def discover_numbered_candidates(document: str) -> tuple[str, ...]:
    """Return stable unique article links; disregard feed prose and quantities.

    Only direct entry/alternate links are eligible. Pagination is deliberately
    not returned as an article, nor followed. Runtime must enforce publisher
    access policy, response bounds and pacing before calling this pure parser.
    """
    if len(document.encode("utf-8")) > 1_000_000:
        raise CollectorError("numbered discovery exceeds response bound")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", document, re.I):
        raise CollectorError("numbered discovery declarations are not supported")
    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as error:
        raise CollectorError("invalid numbered discovery XML") from error
    if root.tag != ATOM + "feed":
        raise CollectorError("numbered discovery is not an Atom feed")
    entries = root.findall(ATOM + "entry")
    if len(entries) > 200:
        raise CollectorError("numbered discovery exceeds entry bound")
    candidates: set[str] = set()
    for entry in entries:
        # Conflicting article identities within one entry are not guessed.
        links = {
            link.get("href", "")
            for link in entry.findall(ATOM + "link")
            if link.get("rel", "alternate") == "alternate"
            and ARTICLE.fullmatch(link.get("href", ""))
        }
        if len(links) == 1:
            candidates.update(links)
    return tuple(sorted(candidates))
