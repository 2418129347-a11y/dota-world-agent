"""Bounded public editorial evidence. None of this text is an instruction or a fact checker."""
from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlencode, urlsplit

from .collectors import USER_AGENT, fetch_json
from .models import NewsItem
from .utils import clean_text, stable_id


def remaining_timeout(deadline: float, maximum: float = 15) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("enrichment budget exhausted")
    return min(maximum, remaining)


def evidence(item: NewsItem, kind: str, text: str, url: str, name: str, **extra: Any) -> dict:
    row = {"id": stable_id(kind, url, text[:100]), "kind": kind, "text": text[:6000],
           "url": url, "source": name, **extra}
    rows = item.metadata.setdefault("editorial_evidence", [])
    if not any(value["id"] == row["id"] for value in rows):
        rows.append(row)
    return row


def seed_evidence(item: NewsItem) -> None:
    if item.summary:
        # An account link alone is not the announcement body.
        kind = "discovery" if item.metadata.get("kind") == "official_reference" else (
            "community" if item.source_tier == "community" else "source_summary")
        evidence(item, kind, item.title + "\n" + item.summary, item.url, item.source_name)


class ArticleText(HTMLParser):
    """Only extract prose in article/main containers, not an arbitrary page's nav."""
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool, bool]] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "img", "meta", "link", "input", "hr", "source"}:
            return
        values = dict(attrs)
        parent_active = self.stack[-1][1] if self.stack else False
        parent_skip = self.stack[-1][2] if self.stack else False
        active = parent_active or tag in {"article", "main"} or values.get("itemprop") == "articleBody"
        skip = parent_skip or tag in {"script", "style", "nav", "footer", "header", "aside", "form", "noscript"}
        marker = " ".join(str(values.get(key) or "") for key in ("class", "id"))
        skip = skip or bool(re.search(r"\b(advert\w*|cookie\w*|related|social|share|newsletter|paywall)\b", marker, re.I))
        self.stack.append((tag, active, skip))
        if tag in {"p", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if tag in {"p", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.stack and self.stack[-1][1] and not self.stack[-1][2]:
            self.parts.append(data)

    def text(self) -> str:
        unique = dict.fromkeys(clean_text(value, 6000) for value in "".join(self.parts).splitlines())
        return "\n".join(value for value in unique if len(value) >= 20)[:6000]


def allowed_url(url: str, domains: list[str]) -> bool:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in {None, 443}
            and any(host == domain or host.endswith("." + domain) for domain in domains))


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, domains: list[str], can_redirect=None) -> None:
        self.domains, self.can_redirect = domains, can_redirect

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl, self.domains):
            raise ValueError("redirect outside public source allowlist")
        if self.can_redirect:
            self.can_redirect(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PublicReader:
    def __init__(self, domains: list[str], deadline: float) -> None:
        self.domains, self.deadline = domains, deadline
        self.robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self.opener = urllib.request.build_opener(SafeRedirect(domains))

    def _get(self, url: str, check_redirect_robots: bool = False) -> tuple[str, str]:
        if not allowed_url(url, self.domains):
            raise ValueError("source outside allowlist")
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        opener = urllib.request.build_opener(SafeRedirect(self.domains, self._check_robots)) if check_redirect_robots else self.opener
        with opener.open(req, timeout=remaining_timeout(self.deadline)) as response:
            raw = response.read(3_000_001)
            if len(raw) > 3_000_000:
                raise ValueError("public response exceeds size limit")
            return raw.decode("utf-8", errors="replace"), response.geturl()

    def _check_robots(self, url: str) -> None:
        if not allowed_url(url, self.domains):
            raise ValueError("source outside allowlist")
        origin = "https://" + str(urlsplit(url).hostname)
        if origin not in self.robots:
            raw, final = self._get(origin + "/robots.txt")
            if urlsplit(final).hostname != urlsplit(origin).hostname:
                raise ValueError("robots origin mismatch")
            robot = urllib.robotparser.RobotFileParser()
            robot.parse(raw.splitlines())
            self.robots[origin] = robot
        if not self.robots[origin].can_fetch(USER_AGENT, url):
            raise PermissionError("robots disallows article")

    def article(self, url: str) -> tuple[str, str]:
        self._check_robots(url)
        raw, final = self._get(url, check_redirect_robots=True)
        parser = ArticleText()
        parser.feed(raw)
        body = parser.text()
        if len(body) < 100:
            raise ValueError("no substantive public article body")
        return body, final


TEAM_ALIASES = {
    "lgd gaming": ["LGD", "PSG.LGD"], "team spirit": ["Spirit"],
    "xtreme gaming": ["Xtreme", "XG"], "yakult brothers": ["YB", "YkBros", "Yakult's Brothers"],
    "team liquid": ["Liquid"], "team falcons": ["Falcons"], "team yandex": ["Yandex"],
    "betboom team": ["BetBoom", "BB Team"], "vici gaming": ["Vici", "VG"],
}
EVENT_ALIASES = {"The International": ["TI"], "The International 2026": ["TI 2026", "TI2026", "The International"],
                 "PGL Wallachia": ["Wallachia"], "BLAST SLAM": ["BLAST"], "Esports World Cup": ["EWC"]}


def post_matches(item: NewsItem, raw: dict) -> bool:
    """Require both teams, event and a nearby publication; reject generic live hubs."""
    text = clean_text(str(raw.get("title") or "") + " " + str(raw.get("selftext") or ""), 6000).casefold()
    if not re.search(r"post[- ]match|match discussion|赛后|复盘", text):
        return False
    if re.search(r"live discussion|megathread|daily discussion|实时讨论", text):
        return False
    def mentioned(name: str) -> bool:
        return bool(name) and bool(re.search(r"(?<!\w)" + re.escape(name.casefold()) + r"(?!\w)", text))
    for key in ("winner", "loser", "league"):
        name = str(item.metadata.get(key) or "")
        aliases = EVENT_ALIASES.get(name, []) if key == "league" else TEAM_ALIASES.get(name.casefold(), [])
        if not any(mentioned(alias) for alias in [name, *aliases]):
            return False
    try:
        published = datetime.fromtimestamp(float(raw["created_utc"]), timezone.utc)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    delta = (published - item.published_at).total_seconds()
    return -3600 <= delta <= 36 * 3600


def useful_comment(raw: dict) -> bool:
    body = clean_text(raw.get("body"), 900)
    return (int(raw.get("score") or 0) >= 5 and len(body) >= 60
            and not re.search(r"\[deleted\]|\[removed\]|\bfuck\w*\b|\bidiot\w*\b|\bkys\b|傻逼|博彩|推广|discord\.gg|https?://", body, re.I)
            and bool(re.search(r"draft|lane|fight|gold|farm|buyback|roshan|timing|item|carry|support|阵容|对线|团战|经济|买活|肉山|节奏|出装", body, re.I)))


def enrich_editorial(items: list[NewsItem], config: dict, deadline: float) -> list[str]:
    warnings: list[str] = []
    settings = config.get("editorial_enrichment", {})
    reader = PublicReader(settings.get("article_domains", []), deadline)
    matches = [item for item in items if item.metadata.get("kind") == "match"]
    rows: list[dict] = []
    if matches:
        try:
            endpoint = settings.get("discussion_posts_url", "")
            if endpoint:
                rows = fetch_json(endpoint, timeout=remaining_timeout(deadline)).get("data", [])
        except Exception as exc:
            warnings.append(f"赛后讨论索引不可用：{type(exc).__name__}")
    for item in items:
        seed_evidence(item)
        states = item.metadata.setdefault("enrichment", {})
        if item.metadata.get("kind") != "match":
            try:
                if not allowed_url(item.url, reader.domains):
                    states["article"] = "not_allowlisted_or_aggregator"
                    continue
                body, final = reader.article(item.url)
                evidence(item, "article", body, final, item.source_name)
                states["article"] = "available"
            except Exception as exc:
                states["article"] = type(exc).__name__
                warnings.append(f"条目 {item.item_id} 正文不可用：{type(exc).__name__}")
            continue
        candidates = sorted((row for row in rows if post_matches(item, row)),
                            key=lambda row: float(row.get("created_utc") or 0), reverse=True)[:2]
        states["discussion"] = "index_unavailable" if warnings and not rows else "no_matching_public_post"
        for raw in candidates:
            post_id = str(raw.get("id") or "")
            if not re.fullmatch(r"[a-z0-9]+", post_id):
                continue
            post_url = f"https://www.reddit.com/r/DotA2/comments/{post_id}/"
            body = clean_text(raw.get("selftext"), 3000)
            if len(body) >= 100:
                evidence(item, "community", body, post_url, "r/DotA2 赛后讨论",
                         published_at=raw.get("created_utc"))
                states["discussion"] = "available"
            try:
                query = urlencode({"link_id": post_id, "limit": 100, "fields": "id,body,score,created_utc"})
                endpoint = settings.get("discussion_comments_url", "")
                comments = fetch_json(endpoint + "?" + query, timeout=remaining_timeout(deadline)).get("data", [])
                seen: set[str] = set()
                for comment in sorted(comments, key=lambda row: int(row.get("score") or 0), reverse=True):
                    text = clean_text(comment.get("body"), 900)
                    cid = str(comment.get("id") or "")
                    if useful_comment(comment) and text not in seen and re.fullmatch(r"[a-z0-9]+", cid):
                        seen.add(text)
                        evidence(item, "community", text, post_url + cid + "/", "r/DotA2 赛后评论",
                                 score=int(comment.get("score") or 0), published_at=comment.get("created_utc"))
                        states["discussion"] = "available"
                    if len(seen) >= 5:
                        break
            except Exception as exc:
                states["discussion"] = type(exc).__name__
                warnings.append(f"比赛 {item.item_id} 评论不可用：{type(exc).__name__}")
    return warnings
