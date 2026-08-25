from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode, urlsplit

from .models import NewsItem
from .utils import clean_text, parse_datetime, stable_id


USER_AGENT = "DotaWorldDigest/0.1 (+https://github.com/)"


def _request(url: str, timeout: int = 15) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/atom+xml, application/rss+xml, text/xml;q=0.9, */*;q=0.5"})
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return response.read(3_000_000)


def fetch_json(url: str, timeout: int = 15) -> Any:
    return json.loads(_request(url, timeout).decode("utf-8", errors="replace"))


def fetch_json_retry(url: str, timeout: int = 20, attempts: int = 2) -> Any:
    for attempt in range(attempts):
        try:
            return fetch_json(url, timeout)
        except urllib.error.HTTPError as exc:
            if attempt + 1 >= attempts or exc.code not in {422, 429, 500, 502, 503, 504}:
                raise
    raise RuntimeError("JSON request exhausted retries")


def collect_steam(source: dict[str, Any], now: datetime) -> list[NewsItem]:
    payload = fetch_json(source["url"])
    items: list[NewsItem] = []
    for raw in payload.get("appnews", {}).get("newsitems", []):
        title = clean_text(raw.get("title"), 300)
        url = str(raw.get("url") or "https://www.dota2.com/news")
        summary = clean_text(raw.get("contents"), 1200)
        published = parse_datetime(raw.get("date"), now)
        feed = clean_text(raw.get("feedlabel") or raw.get("feedname") or "", 100)
        category = "official"
        lower = f"{title} {summary}".lower()
        if any(word in lower for word in ("patch", "gameplay update", "更新", "补丁")):
            category = "patch"
        elif any(word in lower for word in ("international", "tournament", "champion")):
            category = "esports"
        item_id = str(raw.get("gid") or stable_id(source["id"], url, title))
        items.append(NewsItem(item_id, title, url, published, source["id"], source["name"], source["tier"], int(source["trust"]), summary, category, [feed] if feed else []))
    return items


def collect_opendota(source: dict[str, Any], now: datetime) -> list[NewsItem]:
    payload = fetch_json(source["url"])
    items: list[NewsItem] = []
    for raw in payload[:100]:
        radiant = clean_text(raw.get("radiant_name") or "Radiant", 100)
        dire = clean_text(raw.get("dire_name") or "Dire", 100)
        league = clean_text(raw.get("league_name") or "职业赛事", 120)
        radiant_score = raw.get("radiant_score")
        dire_score = raw.get("dire_score")
        radiant_win = bool(raw.get("radiant_win"))
        winner = radiant if radiant_win else dire
        title = f"{league}：{radiant} {radiant_score}–{dire_score} {dire}"
        summary = f"{winner} 赢得本局。比赛数据来自 OpenDota。"
        match_id = str(raw.get("match_id") or stable_id(source["id"], "", title))
        url = f"https://www.opendota.com/matches/{match_id}"
        metadata = {
            "kind": "match",
            "match_id": match_id,
            "match_ids": [match_id],
            "series_id": str(raw.get("series_id") or ""),
            "league": league,
            "radiant": radiant,
            "dire": dire,
            "radiant_score": radiant_score,
            "dire_score": dire_score,
            "winner": winner,
            "loser": dire if radiant_win else radiant,
        }
        items.append(NewsItem(match_id, title, url, parse_datetime(raw.get("start_time"), now), source["id"], source["name"], source["tier"], int(source["trust"]), summary, "esports", [league], metadata=metadata))
    return items


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ET.Element, names: tuple[str, ...]) -> str:
    for child in element.iter():
        if _local_name(child.tag) in names and child.text:
            return child.text
    return ""


def _entry_link(element: ET.Element) -> str:
    for child in element.iter():
        if _local_name(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href
            if child.text:
                return child.text.strip()
    return ""


def collect_rss(source: dict[str, Any], now: datetime) -> list[NewsItem]:
    root = ET.fromstring(_request(source["url"]))
    entries = [element for element in root.iter() if _local_name(element.tag) in {"item", "entry"}]
    items: list[NewsItem] = []
    for entry in entries[:60]:
        title = clean_text(_child_text(entry, ("title",)), 300)
        url = _entry_link(entry)
        if not title or not url:
            continue
        publisher = clean_text(_child_text(entry, ("source",)), 100) if source.get("publisher_from_feed") else ""
        allowed_publishers = [str(value).casefold() for value in source.get("allowed_publishers", [])]
        if allowed_publishers and publisher.casefold() not in allowed_publishers:
            continue
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -(len(publisher) + 3)].strip()
        summary = clean_text(_child_text(entry, ("summary", "description", "content")), 1200)
        published = parse_datetime(_child_text(entry, ("published", "updated", "pubdate", "date")), now)
        item_id = clean_text(_child_text(entry, ("id", "guid")), 300) or stable_id(source["id"], url, title)
        source_name = publisher or source["name"]
        source_id = f"{source['id']}:{publisher.casefold().replace(' ', '-')}" if publisher else source["id"]
        items.append(NewsItem(item_id, title, url, published, source_id, source_name, source["tier"], int(source["trust"]), summary, "community"))
    return items


def _official_reference(url: str, source: dict[str, Any]) -> dict[str, Any] | None:
    if not url:
        return None
    parsed = urlsplit(url)
    domain = parsed.netloc.casefold().removeprefix("www.")
    path = parsed.path.casefold()
    for reference in source.get("official_references", []):
        expected_domain = str(reference.get("domain") or "").casefold().removeprefix("www.")
        expected_path = str(reference.get("path_prefix") or "/").casefold()
        if domain == expected_domain and path.startswith(expected_path):
            return reference
    return None


def collect_reddit(source: dict[str, Any], now: datetime) -> list[NewsItem]:
    payload = fetch_json_retry(source["url"], timeout=30)
    thresholds = source.get("engagement", {})
    min_score = int(thresholds.get("min_score", 0))
    min_comments = int(thresholds.get("min_comments", 0))
    comment_cap = max(min_comments, int(thresholds.get("comment_cap", 100)))
    keywords = [str(value).casefold() for value in source.get("interest_keywords", [])]
    topic_keywords = [str(value).casefold() for value in source.get("topic_keywords", [])]
    candidate_limit = int(source.get("engagement_candidate_limit", 8))
    comments_api = str(source.get("comments_api") or "https://arctic-shift.photon-reddit.com/api/comments/search")
    items: list[NewsItem] = []
    candidate_count = 0
    def keyword_match(keyword: str, value: str) -> bool:
        return (
            re.search(rf"(?<![a-z0-9_]){re.escape(keyword)}(?![a-z0-9_])", value) is not None
            if re.fullmatch(r"[a-z0-9_-]+", keyword)
            else keyword in value
        )

    for raw in payload.get("data", []):
        post_id = clean_text(raw.get("id"), 30)
        title = clean_text(raw.get("title"), 300)
        summary = clean_text(raw.get("selftext"), 1200)
        external_url = str(raw.get("url") or "")
        official_reference = _official_reference(external_url, source)
        if not post_id or not title:
            continue
        text = f"{title} {summary}".casefold()
        shuffle_hub = bool(re.search(r"post[- ]ti.*shuffle", text)) or any(
            term in text for term in ("roster shuffle", "shuffle rumor", "shuffle rumour")
        )
        if keywords and not any(keyword_match(keyword, text) for keyword in keywords) and not shuffle_hub:
            continue
        if topic_keywords and not any(keyword in text for keyword in topic_keywords) and not official_reference:
            continue
        candidate_count += 1
        if candidate_count > candidate_limit:
            break
        if official_reference:
            source_name = clean_text(official_reference.get("name"), 100) or "官方公告"
            official_summary = (
                f"这是经 {source['name']} 发现的 {source_name} 官方公告链接。"
                "处罚或纪律事实以原公告为准；社区评论及后续调查帖中的额外指控不视为已确认事实。"
            )
            item = NewsItem(
                f"official-ref-{post_id}", title, external_url, parse_datetime(raw.get("created_utc"), now),
                str(official_reference.get("id") or f"official:{source_name}"), source_name, "official",
                int(official_reference.get("trust", 95)), official_summary, "community",
            )
        else:
            url = f"https://www.reddit.com/r/DotA2/comments/{post_id}/"
            item = NewsItem(
                f"t3_{post_id}", title, url, parse_datetime(raw.get("created_utc"), now),
                source["id"], source["name"], source["tier"], int(source["trust"]),
                summary, "community",
            )
        try:
            embed_url = f"https://embed.reddit.com/r/DotA2/comments/{post_id}/"
            embed_html = _request(embed_url, timeout=10).decode("utf-8", errors="replace")
            score_match = re.search(
                r'<faceplate-number\s+number="(\d+)"[^>]*></faceplate-number>\s*upvotes',
                embed_html,
                flags=re.IGNORECASE,
            )
            score = int(score_match.group(1)) if score_match else 0
            if score < min_score:
                continue
            query = urlencode({"link_id": post_id, "limit": comment_cap, "fields": "id,body,score,created_utc"})
            comment_payload = fetch_json_retry(f"{comments_api}?{query}", timeout=15)
            comment_rows = comment_payload.get("data", [])
            comments = len(comment_rows)
        except Exception:
            continue
        if comments < min_comments:
            continue
        movement_signals = []
        if shuffle_hub:
            ranked_comments = sorted(comment_rows, key=lambda value: int(value.get("score") or 0), reverse=True)
            for comment in ranked_comments:
                body = clean_text(comment.get("body"), 500)
                lowered = body.casefold()
                if (
                    body
                    and body not in movement_signals
                    and any(keyword_match(keyword, lowered) for keyword in keywords)
                ):
                    movement_signals.append(body)
                if len(movement_signals) >= 6:
                    break
            if movement_signals:
                summary = "Post-TI 转会集中讨论中的高热度线索：" + " / ".join(movement_signals)
                item.summary = clean_text(summary, 1200)
        item.metadata = {
            "kind": "official_reference" if official_reference else "forum_post",
            "engagement": {
                "score": score,
                "comments": comments,
                "comments_capped": comments >= comment_cap,
            },
            "movement_signals": movement_signals,
        }
        if official_reference:
            item.metadata.update({
                "discovered_via": source["name"],
                "verification_status": "official_action_confirmed",
            })
        items.append(item)
    return items


def collect_all(config: dict[str, Any], now: datetime | None = None) -> tuple[list[NewsItem], list[str]]:
    now = now or datetime.now(timezone.utc)
    items: list[NewsItem] = []
    warnings: list[str] = []
    jobs: list[tuple[str, Any, dict[str, Any]]] = []
    if config.get("steam", {}).get("enabled"):
        jobs.append((config["steam"]["name"], collect_steam, config["steam"]))
    if config.get("opendota", {}).get("enabled"):
        jobs.append((config["opendota"]["name"], collect_opendota, config["opendota"]))
    for source in config.get("rss", []):
        if source.get("enabled"):
            collector = collect_reddit if source.get("format") == "reddit_engagement" else collect_rss
            jobs.append((source["name"], collector, source))
    for name, collector, source in jobs:
        try:
            items.extend(collector(source, now))
        except Exception as exc:
            warnings.append(f"{name} 采集失败：{type(exc).__name__}: {exc}")
    return items, warnings
