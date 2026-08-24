from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit

from .models import NewsItem
from .utils import canonical_url, normalize_title, title_tokens
from .editorial import apply_editorial_priority


CATEGORY_LABELS = {
    "official": "官方与版本",
    "patch": "官方与版本",
    "esports": "全球焦点赛事",
    "roster": "圈内消息",
    "community": "圈内消息",
    "data": "数据洞察",
}


def similarity(a: str, b: str) -> float:
    left, right = title_tokens(a), title_tokens(b)
    if not left or not right:
        return 1.0 if normalize_title(a) == normalize_title(b) else 0.0
    return len(left & right) / len(left | right)


def is_recent(item: NewsItem, now: datetime, hours: int) -> bool:
    age = (now - item.published_at.astimezone(timezone.utc)).total_seconds() / 3600
    return -2 <= age <= hours


def deduplicate(items: list[NewsItem], threshold: float) -> list[NewsItem]:
    ordered = sorted(items, key=lambda item: (item.trust, item.published_at), reverse=True)
    selected: list[NewsItem] = []
    by_url: dict[str, NewsItem] = {}
    for item in ordered:
        url_key = canonical_url(item.url)
        duplicate = by_url.get(url_key)
        if duplicate is None:
            duplicate = next((current for current in selected if similarity(current.title, item.title) >= threshold), None)
        if duplicate is not None:
            if item.source_name != duplicate.source_name and item.source_name not in duplicate.corroborating_sources:
                duplicate.corroborating_sources.append(item.source_name)
            continue
        selected.append(item)
        by_url[url_key] = item
    return selected


def _keyword_score(item: NewsItem, keywords: dict[str, int]) -> int:
    haystack = f"{item.title} {item.summary}".lower()
    return min(30, sum(weight for keyword, weight in keywords.items() if keyword.lower() in haystack))


def score_item(item: NewsItem, now: datetime, keywords: dict[str, int]) -> float:
    age_hours = max(0.0, (now - item.published_at.astimezone(timezone.utc)).total_seconds() / 3600)
    recency = max(0.0, 24.0 - age_hours) * 0.8
    corroboration = min(20, len(item.corroborating_sources) * 10)
    tier_bonus = {"official": 20, "data": 7, "media": 5, "community": 0}.get(item.source_tier, 0)
    sensitive_penalty = 0
    lower = f"{item.title} {item.summary}".lower()
    if any(word in lower for word in ("match fixing", "match-fixing", "ban", "banned", "假赛", "禁赛")) and item.source_tier != "official" and not item.corroborating_sources:
        sensitive_penalty = 30
    engagement = item.metadata.get("engagement", {})
    engagement_bonus = min(
        25.0,
        int(engagement.get("score") or 0) / 100
        + int(engagement.get("comments") or 0) / 15
    )
    item.score = round(
        item.trust + recency + corroboration + tier_bonus + engagement_bonus
        + _keyword_score(item, keywords) - sensitive_penalty,
        2,
    )
    return item.score


def select_items(
    items: list[NewsItem],
    ranking: dict,
    seen: set[str] | None = None,
    now: datetime | None = None,
    editorial_policy: dict | None = None,
) -> list[NewsItem]:
    now = now or datetime.now(timezone.utc)
    seen = seen or set()
    hours = int(ranking.get("hours", 30))
    rumor_hours = int((editorial_policy or {}).get("community_rumor", {}).get("max_age_hours", hours))
    recent = [
        item
        for item in items
        if (
            is_recent(item, now, hours)
            or (item.metadata.get("kind") == "forum_post" and is_recent(item, now, rumor_hours))
        )
        and item.item_id not in seen
        and canonical_url(item.url) not in seen
    ]
    unique = deduplicate(recent, float(ranking.get("duplicate_similarity", 0.72)))
    for item in unique:
        score_item(item, now, ranking.get("keywords", {}))
    if editorial_policy:
        apply_editorial_priority(unique, editorial_policy, now)
    unique.sort(key=lambda item: (item.score, item.published_at), reverse=True)
    source_counts: dict[str, int] = {}
    result: list[NewsItem] = []
    per_source = int(ranking.get("per_source", 2))
    limit = int(ranking.get("limit", 8))
    min_score = float(ranking.get("min_score", 0))
    community_min_score = float(ranking.get("community_min_score", min_score))
    for item in unique:
        threshold = community_min_score if item.source_tier == "community" else min_score
        if item.metadata.get("community_rumor"):
            threshold = 0
        if item.score < threshold:
            continue
        if editorial_policy and item.source_tier in {"media", "community"} and not item.priority_group:
            continue
        if item.source_tier != "official" and item.priority_group != "china_match" and source_counts.get(item.source_id, 0) >= per_source:
            continue
        result.append(item)
        source_counts[item.source_id] = source_counts.get(item.source_id, 0) + 1
        if len(result) >= limit:
            break
    return result


def section_for(item: NewsItem) -> str:
    if item.priority_group == "tier1_schedule":
        return "Tier 1 赛程提醒"
    if item.priority_group == "china_match":
        return "中国 Dota 赛场"
    if item.priority_group == "global_match":
        return "全球焦点赛事"
    if item.priority_group == "circle":
        return "圈内消息"
    if item.priority_group == "legend":
        return "传奇选手动态"
    if item.category == "community" and item.source_tier == "data":
        return "数据洞察"
    return CATEGORY_LABELS.get(item.category, "社区热点")


def source_label(item: NewsItem) -> str:
    if item.metadata.get("kind") == "tier1_reminder":
        return "赛程核验"
    if item.metadata.get("community_rumor"):
        return "社区传闻"
    labels = {"official": "官方", "data": "数据源", "media": "媒体", "community": "社区"}
    return labels.get(item.source_tier, item.source_tier)


def display_domain(url: str) -> str:
    return urlsplit(url).netloc.removeprefix("www.")
