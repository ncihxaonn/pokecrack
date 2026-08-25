"""Small HTML-to-metadata parser used only by bounded fixture adapters."""

from __future__ import annotations

from html.parser import HTMLParser


class MetadataHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._capture: str | None = None
        self._hidden_depth = 0
        self.title: list[str] = []
        self.heading: list[str] = []
        self.paragraphs: list[str] = []
        self._paragraph: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.casefold()
        if tag in {"script", "style", "noscript"}:
            self._hidden_depth += 1
        elif not self._hidden_depth and tag in {"title", "h1", "p"}:
            self._capture = tag
            if tag == "p":
                self._paragraph = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in {"script", "style", "noscript"} and self._hidden_depth:
            self._hidden_depth -= 1
            return
        if tag == "p" and self._capture == "p":
            paragraph = " ".join("".join(self._paragraph).split())
            if paragraph:
                self.paragraphs.append(paragraph)
        if tag == self._capture:
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._hidden_depth or not data.strip():
            return
        if self._capture == "title":
            self.title.append(data)
        elif self._capture == "h1":
            self.heading.append(data)
        elif self._capture == "p":
            self._paragraph.append(data)


def parse_metadata(body: bytes, *, max_text_chars: int) -> tuple[str | None, str | None]:
    parser = MetadataHTMLParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    parser.close()
    title = " ".join("".join(parser.heading or parser.title).split()) or None
    text = parser.paragraphs[0][:max_text_chars] if parser.paragraphs else None
    return title, text
