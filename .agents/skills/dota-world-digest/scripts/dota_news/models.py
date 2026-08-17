from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class NewsItem:
    item_id: str
    title: str
    url: str
    published_at: datetime
    source_id: str
    source_name: str
    source_tier: str
    trust: int
    summary: str = ""
    category: str = "community"
    tags: list[str] = field(default_factory=list)
    corroborating_sources: list[str] = field(default_factory=list)
    score: float = 0.0
    title_zh: str = ""
    summary_zh: str = ""
    why_it_matters: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["published_at"] = self.published_at.astimezone(timezone.utc).isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NewsItem":
        payload = dict(data)
        published = payload.get("published_at")
        if isinstance(published, str):
            payload["published_at"] = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if payload["published_at"].tzinfo is None:
            payload["published_at"] = payload["published_at"].replace(tzinfo=timezone.utc)
        return cls(**payload)
