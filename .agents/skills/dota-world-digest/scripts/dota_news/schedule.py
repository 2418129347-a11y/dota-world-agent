from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .models import NewsItem
from .utils import stable_id


DISPLAY_TZ = ZoneInfo("Asia/Shanghai")


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _event_matches(league: str, names: list[str]) -> bool:
    league_key = _key(league)
    return bool(league_key) and any(name and (_key(name) in league_key or league_key in _key(name)) for name in names)


def _team_set(values: list[str]) -> set[str]:
    return {_key(value) for value in values if value}


def _series_date(entry: dict[str, Any]) -> date | None:
    value = str(entry.get("scheduled_at") or "")
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(DISPLAY_TZ).date()


def apply_verified_schedule_context(items: list[NewsItem], calendar: dict[str, Any]) -> None:
    """Apply advancement/elimination copy only from an exact verified stage snapshot."""
    events = {str(event.get("id")): event for event in calendar.get("events", [])}
    for item in items:
        if item.metadata.get("kind") != "match":
            continue
        league = str(item.metadata.get("league") or "")
        teams = _team_set([
            str(item.metadata.get("winner") or ""),
            str(item.metadata.get("loser") or ""),
        ])
        if len(teams) != 2:
            continue
        for entry in calendar.get("series", []):
            sources = entry.get("sources", [])
            if not entry.get("verified_at") or not entry.get("stage") or "loser_out" not in entry or len(sources) < 2:
                continue
            event = events.get(str(entry.get("event_id") or ""), {})
            event_names = [str(event.get("name") or ""), *[str(value) for value in event.get("aliases", [])]]
            if not _event_matches(league, event_names):
                continue
            if teams != _team_set([str(entry.get("team_a") or ""), str(entry.get("team_b") or "")]):
                continue
            scheduled_date = _series_date(entry)
            result_date = item.published_at.astimezone(DISPLAY_TZ).date()
            if scheduled_date and abs((result_date - scheduled_date).days) > 1:
                continue
            winner = str(item.metadata.get("winner") or "")
            loser = str(item.metadata.get("loser") or "")
            winner_destination = str(entry.get("winner_destination") or "下一轮")
            loser_destination = str(entry.get("loser_destination") or "")
            if bool(entry.get("loser_out")):
                item.impact = f"{winner} 晋级{winner_destination}；{loser} 在该淘汰轮失利后结束本届赛事征程。"
            elif loser_destination:
                item.impact = f"{winner} 晋级{winner_destination}；{loser} 落入{loser_destination}，尚未出局。"
            else:
                item.impact = f"{winner} 晋级{winner_destination}；{loser} 的后续去向以赛事官方赛程为准。"
            item.metadata.update({
                "verification_status": "schedule_stage_confirmed",
                "schedule_stage": entry.get("stage_zh") or entry.get("stage"),
                "loser_out": bool(entry.get("loser_out")),
            })
            for source in sources:
                name = str(source.get("name") or "")
                if name and name not in item.corroborating_sources:
                    item.corroborating_sources.append(name)
            break


def build_tier1_reminders(calendar: dict[str, Any], now: datetime, seen: set[str]) -> list[NewsItem]:
    local_now = now.astimezone(DISPLAY_TZ)
    reminders: list[NewsItem] = []
    for event in calendar.get("events", []):
        if not event.get("reminder", False):
            continue
        if not event.get("verified_at") or not event.get("sources"):
            continue
        starts_on = date.fromisoformat(str(event["starts_on"]))
        lead_days = int(event.get("reminder_days_before", calendar.get("reminder_days_before", 1)))
        fixtures = []
        for fixture in event.get("fixtures", []):
            required = ("scheduled_at", "team_a", "team_b", "stage_zh", "best_of", "verified_at", "source_url")
            if not all(fixture.get(field) not in (None, "") for field in required):
                continue
            scheduled = datetime.fromisoformat(str(fixture["scheduled_at"]).replace("Z", "+00:00")).astimezone(DISPLAY_TZ)
            fixtures.append({**fixture, "scheduled_at": scheduled.isoformat()})
        fixtures.sort(key=lambda value: value["scheduled_at"])
        lookahead_days = int(calendar.get("schedule_lookahead_days", 1))
        upcoming_fixtures = [
            fixture for fixture in fixtures
            if 0 <= (
                datetime.fromisoformat(str(fixture["scheduled_at"])).astimezone(DISPLAY_TZ).date() - local_now.date()
            ).days <= lookahead_days
        ]
        event_reminder_due = (starts_on - local_now.date()).days == lead_days
        if not event_reminder_due and not upcoming_fixtures:
            continue
        event_id = str(event["id"])
        item_id = stable_id("tier1-schedule", event_id, local_now.date().isoformat())
        if item_id in seen:
            continue
        sources = event.get("sources", [])
        primary = sources[0] if sources else {}
        end = str(event.get("ends_on") or event["starts_on"])
        date_text = starts_on.strftime("%m月%d日")
        if end != event["starts_on"]:
            date_text += f"至{date.fromisoformat(end).strftime('%m月%d日')}"
        note = str(event.get("schedule_note") or "具体对阵和开赛时间以赛事官方赛程为准。")
        title = f"具体赛程：{event['name']}"
        if upcoming_fixtures:
            note = f"未来 {lookahead_days + 1} 天已核验 {len(upcoming_fixtures)} 场具体对阵；时间均为北京时间。"
        reminders.append(NewsItem(
            item_id=item_id,
            title=title,
            title_zh=title,
            url=str(primary.get("url") or ""),
            published_at=now,
            source_id=f"tier1-calendar-{event_id}",
            source_name=str(primary.get("name") or "赛事官方赛程"),
            source_tier="official",
            trust=95,
            category="schedule",
            summary=f"赛事日期：{date_text}。{note}",
            summary_zh=f"赛事日期：{date_text}。{note}",
            impact="已建立赛前赛程快照；赛后只有在赛事、双方与赛制阶段全部匹配时，才会写入晋级或淘汰结论。",
            priority_group="tier1_schedule",
            corroborating_sources=[str(source.get("name")) for source in sources[1:] if source.get("name")],
            metadata={
                "kind": "tier1_reminder", "event_id": event_id, "event_name": event["name"],
                "tier": event.get("tier", 1), "date_text": date_text,
                "fixtures": upcoming_fixtures, "schedule_pending": not bool(upcoming_fixtures),
            },
        ))
    return reminders
