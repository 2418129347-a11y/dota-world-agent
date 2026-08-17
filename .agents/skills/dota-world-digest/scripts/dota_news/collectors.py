from __future__ import annotations

import json
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

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
        summary = f"{winner} 赢得本场比赛。比赛数据来自 OpenDota；赛果应在重要赛事原始页面再次核验。"
        match_id = str(raw.get("match_id") or stable_id(source["id"], "", title))
        url = f"https://www.opendota.com/matches/{match_id}"
        items.append(NewsItem(match_id, title, url, parse_datetime(raw.get("start_time"), now), source["id"], source["name"], source["tier"], int(source["trust"]), summary, "esports", [league]))
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
        summary = clean_text(_child_text(entry, ("summary", "description", "content")), 1200)
        published = parse_datetime(_child_text(entry, ("published", "updated", "pubdate", "date")), now)
        item_id = clean_text(_child_text(entry, ("id", "guid")), 300) or stable_id(source["id"], url, title)
        items.append(NewsItem(item_id, title, url, published, source["id"], source["name"], source["tier"], int(source["trust"]), summary, "community"))
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
            jobs.append((source["name"], collect_rss, source))
    for name, collector, source in jobs:
        try:
            items.extend(collector(source, now))
        except Exception as exc:
            warnings.append(f"{name} 采集失败：{type(exc).__name__}: {exc}")
    return items, warnings
