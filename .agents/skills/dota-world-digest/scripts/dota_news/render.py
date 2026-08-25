from __future__ import annotations

import html
import os
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from .models import NewsItem
from .pipeline import section_for, source_label


SECTION_ORDER = ["中国 Dota 赛场", "中国 Dota 动态", "转会期情报（T1）", "近期赛程", "全球焦点赛事", "圈内消息", "传奇选手动态", "官方与版本", "数据洞察"]
DISPLAY_TZ = ZoneInfo(os.environ.get("DIGEST_TIMEZONE", "Asia/Shanghai"))


def subject_for(items: list[NewsItem], date_label: str) -> str:
    lead = (items[0].title_zh or items[0].title) if items else "今日暂无重要更新"
    if len(lead) > 34:
        lead = lead[:33] + "…"
    label = "刀塔世界日报·含赛程提醒" if any(item.metadata.get("kind") == "tier1_reminder" for item in items) else "刀塔世界日报"
    return f"【{label}】{lead}｜{date_label}"


def _item_html(item: NewsItem, index: int) -> str:
    corroboration = ""
    if item.corroborating_sources:
        corroboration = f'<div class="corroboration">交叉来源：{html.escape("、".join(item.corroborating_sources))}</div>'
    engagement_html = ""
    engagement = item.metadata.get("engagement", {})
    if item.metadata.get("community_rumor") and engagement:
        comments_suffix = "+" if engagement.get("comments_capped") else ""
        engagement_html = (
            '<div class="corroboration">社区热度：'
            f'{int(engagement.get("score") or 0):,} 赞同 · '
            f'{int(engagement.get("comments") or 0):,}{comments_suffix} 条评论</div>'
        )
    verification_html = ""
    if item.metadata.get("verification_status") == "official_action_confirmed":
        verification_html = '<div class="corroboration">核验状态：纪律处罚已有官方出处 · 具体违规过程以原公告为准</div>'
    elif item.metadata.get("verification_status") == "schedule_stage_confirmed":
        stage = html.escape(str(item.metadata.get("schedule_stage") or "赛程阶段"))
        verification_html = f'<div class="corroboration">核验状态：比赛结果与{stage}赛程快照已匹配</div>'
    elif item.metadata.get("movement_status"):
        verification_html = f'<div class="corroboration">动向状态：{html.escape(str(item.metadata["movement_status"]))}</div>'
    notes = []
    if item.impact:
        notes.append(f'<div class="impact"><strong>赛事影响</strong><span>{html.escape(item.impact)}</span></div>')
    if item.editorial_note:
        notes.append(f'<div class="editorial"><strong>编辑点评</strong><span>{html.escape(item.editorial_note)}</span></div>')
    if not notes and item.why_it_matters:
        notes.append(f'<div class="impact"><strong>值得关注</strong><span>{html.escape(item.why_it_matters)}</span></div>')
    spotlights = []
    for spotlight in item.spotlights:
        damage = int(spotlight.get("hero_damage") or 0)
        damage_text = f" · 英雄伤害 {damage:,}" if damage else ""
        spotlights.append(
            '<div class="spotlight">'
            f'<span class="spotlight-label">{html.escape(str(spotlight.get("label") or "本场最佳"))}</span>'
            f'<strong>{html.escape(str(spotlight.get("player") or ""))}</strong>'
            f'<span>{html.escape(str(spotlight.get("team") or ""))} · {html.escape(str(spotlight.get("role") or ""))}</span>'
            f'<span>{html.escape(str(spotlight.get("hero") or ""))} · KDA {html.escape(str(spotlight.get("kda") or ""))}{damage_text}</span>'
            '</div>'
        )
    return f"""
<article class="news-card">
  <div class="news-index">{index:02d}</div>
  <div class="news-body">
    <div class="meta"><span class="tier tier-{html.escape(item.source_tier)}">{html.escape(source_label(item))}</span><span>{html.escape(item.source_name)}</span><span>{item.published_at.astimezone(DISPLAY_TZ).strftime('%m-%d %H:%M')}</span></div>
    <h3><a href="{html.escape(item.url, quote=True)}">{html.escape(item.title_zh or item.title)}</a></h3>
    <p>{html.escape(item.summary_zh or item.summary)}</p>
    {''.join(spotlights)}
    {''.join(notes)}
    {engagement_html}
    {verification_html}
    {corroboration}
  </div>
</article>""".strip()


def _schedule_html(item: NewsItem, index: int) -> str:
    fixtures = item.metadata.get("fixtures", [])
    rows = []
    for fixture in fixtures:
        scheduled = datetime.fromisoformat(str(fixture["scheduled_at"]).replace("Z", "+00:00")).astimezone(DISPLAY_TZ)
        elimination = "淘汰局" if fixture.get("loser_out") else "非淘汰局"
        rows.append(
            '<div class="fixture-row">'
            f'<div class="fixture-time">{scheduled.strftime("%m-%d")}<strong>{scheduled.strftime("%H:%M")}</strong></div>'
            '<div class="fixture-match">'
            f'<strong>{html.escape(str(fixture.get("team_a") or "待定"))}</strong>'
            '<span class="versus">VS</span>'
            f'<strong>{html.escape(str(fixture.get("team_b") or "待定"))}</strong>'
            f'<small>{html.escape(str(fixture.get("stage_zh") or "阶段待定"))} · {html.escape(str(fixture.get("best_of") or "赛制待定"))} · {elimination}</small>'
            '</div></div>'
        )
    if not rows:
        rows.append('<div class="schedule-pending">具体对阵尚未由可核验来源公布；不会猜测队伍、开赛时间或淘汰阶段。</div>')
    corroboration = ""
    if item.corroborating_sources:
        corroboration = f'<div class="corroboration">赛程复核：{html.escape("、".join(item.corroborating_sources))}</div>'
    return f"""
<article class="schedule-card">
  <div class="news-index">{index:02d}</div>
  <div class="news-body">
    <div class="meta"><span class="tier tier-official">赛程核验</span><span>{html.escape(item.source_name)}</span><span>北京时间</span></div>
    <h3><a href="{html.escape(item.url, quote=True)}">{html.escape(item.title_zh or item.title)}</a></h3>
    <p>{html.escape(item.summary_zh or item.summary)}</p>
    <div class="fixture-board">{''.join(rows)}</div>
    {corroboration}
  </div>
</article>""".strip()


def render_html(items: list[NewsItem], template_path: Path, generated_at: datetime, warnings: list[str]) -> tuple[str, str]:
    date_label = generated_at.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d")
    subject = subject_for(items, date_label)
    sections: OrderedDict[str, list[NewsItem]] = OrderedDict((name, []) for name in SECTION_ORDER)
    for item in items:
        sections.setdefault(section_for(item), []).append(item)
    blocks: list[str] = []
    index = 1
    for section, section_items in sections.items():
        if not section_items:
            continue
        cards = []
        for item in section_items:
            cards.append(_schedule_html(item, index) if item.metadata.get("kind") == "tier1_reminder" else _item_html(item, index))
            index += 1
        blocks.append(f'<section><h2>{html.escape(section)}</h2>{"".join(cards)}</section>')
    if not blocks:
        blocks.append('<section class="empty"><h2>今日暂无重要更新</h2><p>采集流程已完成，但没有符合时间窗和质量阈值的条目。</p></section>')
    warning_html = ""
    if warnings:
        warning_html = '<div class="warnings"><strong>来源状态：</strong>' + html.escape("；".join(warnings)) + "</div>"
    template = Template(template_path.read_text(encoding="utf-8"))
    reminder_count = sum(item.metadata.get("kind") == "tier1_reminder" for item in items)
    subtitle = f"中国 Dota 全量追踪 · 全球焦点精选 · 今日收录 {len(items)} 条"
    if reminder_count:
        subtitle += f" · Tier 1 赛程提醒 {reminder_count} 条"
    rendered = template.safe_substitute(
        subject=html.escape(subject),
        date_label=html.escape(date_label),
        generated_time=html.escape(generated_at.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d %H:%M %Z")),
        item_count=str(len(items)),
        subtitle=html.escape(subtitle),
        item_blocks="".join(blocks),
        warning_block=warning_html,
    )
    return subject, rendered


def render_text(items: list[NewsItem], generated_at: datetime, warnings: list[str]) -> tuple[str, str]:
    date_label = generated_at.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d")
    subject = subject_for(items, date_label)
    lines = [subject, "", f"生成时间：{generated_at.astimezone(DISPLAY_TZ).strftime('%Y-%m-%d %H:%M %Z')}", ""]
    if not items:
        lines.extend(["今日暂无重要更新。", ""])
    for index, item in enumerate(items, 1):
        engagement = item.metadata.get("engagement", {})
        engagement_line = ""
        if item.metadata.get("community_rumor") and engagement:
            comments_suffix = "+" if engagement.get("comments_capped") else ""
            engagement_line = (
                f"   社区热度：{int(engagement.get('score') or 0):,} 赞同 · "
                f"{int(engagement.get('comments') or 0):,}{comments_suffix} 条评论"
            )
        verification_line = ""
        if item.metadata.get("verification_status") == "official_action_confirmed":
            verification_line = "   核验状态：纪律处罚已有官方出处；具体违规过程以原公告为准"
        elif item.metadata.get("verification_status") == "schedule_stage_confirmed":
            verification_line = f"   核验状态：比赛结果与{item.metadata.get('schedule_stage') or '赛程阶段'}快照已匹配"
        elif item.metadata.get("movement_status"):
            verification_line = f"   动向状态：{item.metadata['movement_status']}"
        spotlight_lines = [
            f"   {spotlight.get('label', '本场最佳')}：{spotlight.get('player')}｜{spotlight.get('team')}｜{spotlight.get('role')}｜{spotlight.get('hero')}｜KDA {spotlight.get('kda')}"
            for spotlight in item.spotlights
        ]
        schedule_lines = []
        if item.metadata.get("kind") == "tier1_reminder":
            fixtures = item.metadata.get("fixtures", [])
            if fixtures:
                for fixture in fixtures:
                    scheduled = datetime.fromisoformat(str(fixture["scheduled_at"]).replace("Z", "+00:00")).astimezone(DISPLAY_TZ)
                    elimination = "淘汰局" if fixture.get("loser_out") else "非淘汰局"
                    schedule_lines.append(
                        f"   {scheduled.strftime('%m-%d %H:%M')}｜{fixture.get('team_a')} vs {fixture.get('team_b')}｜{fixture.get('stage_zh')} · {fixture.get('best_of')} · {elimination}"
                    )
            else:
                schedule_lines.append("   具体对阵尚未由可核验来源公布。")
        lines.extend(
            [
                f"{index}. {item.title_zh or item.title}",
                f"   [{source_label(item)}] {item.source_name} · {item.published_at.astimezone(DISPLAY_TZ).strftime('%m-%d %H:%M')}",
                f"   {item.summary_zh or item.summary}",
                *schedule_lines,
                *([engagement_line] if engagement_line else []),
                *([verification_line] if verification_line else []),
                *spotlight_lines,
                *([f"   赛事影响：{item.impact}"] if item.impact else []),
                *([f"   编辑点评：{item.editorial_note}"] if item.editorial_note else []),
                *([f"   值得关注：{item.why_it_matters}"] if item.why_it_matters and not item.impact and not item.editorial_note else []),
                f"   原文：{item.url}",
                "",
            ]
        )
    if warnings:
        lines.extend(["来源状态：", *[f"- {warning}" for warning in warnings], ""])
    lines.append("本邮件只提供信息摘要，不构成投注或投资建议。")
    return subject, "\n".join(lines)
