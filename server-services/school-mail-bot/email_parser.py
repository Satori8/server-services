from html.parser import HTMLParser
import re


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.ignore_tag_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "head"):
            self.ignore_tag_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "head"):
            self.ignore_tag_depth = max(0, self.ignore_tag_depth - 1)

    def handle_data(self, data: str) -> None:
        if self.ignore_tag_depth == 0:
            self.text_parts.append(data)


class EmailParser:
    @staticmethod
    def html_to_text(html_content: str) -> str:
        parser = _HTMLTextExtractor()
        parser.feed(html_content)
        text = "".join(parser.text_parts)

        # Clean up multiple whitespaces and newlines
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()
