from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_KEYS = {"fbclid", "gclid", "ref", "source", "utm_campaign", "utm_content", "utm_medium", "utm_source", "utm_term"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_text(value: str | None, limit: int = 1600) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(value or "")
        text = " ".join(parser.parts)
    except Exception:
        text = html.unescape(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def canonical_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip())
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in TRACKING_KEYS and not k.lower().startswith("utm_")]
        path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(sorted(query)), ""))
    except Exception:
        return url.strip()


def stable_id(source_id: str, url: str, title: str) -> str:
    raw = f"{source_id}|{canonical_url(url)}|{normalize_title(title)}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def normalize_title(title: str) -> str:
    title = clean_text(title, 500).lower()
    title = re.sub(r"[^\w\u4e00-\u9fff]+", " ", title, flags=re.UNICODE)
    return re.sub(r"\s+", " ", title).strip()


def title_tokens(title: str) -> set[str]:
    normalized = normalize_title(title)
    words = set(normalized.split())
    compact_cjk = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    words.update(compact_cjk[i : i + 2] for i in range(max(0, len(compact_cjk) - 1)))
    return {token for token in words if len(token) > 1}


def parse_datetime(value: object, default: datetime | None = None) -> datetime:
    fallback = default or datetime.now(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if not value:
        return fallback
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def compact(value: str, limit: int) -> str:
    value = clean_text(value, max(limit * 2, limit))
    if len(value) <= limit:
        return value
    return value[: max(1, limit - 1)].rstrip() + "…"
