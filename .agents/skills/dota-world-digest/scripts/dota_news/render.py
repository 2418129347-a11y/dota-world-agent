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


SECTION_ORDER = ["今日重点", "官方与版本", "职业赛场", "战队与选手", "社区热点", "数据洞察"]
DISPLAY_TZ = ZoneInfo(os.environ.get("DIGEST_TIMEZONE", "Asia/Shanghai"))


def subject_for(items: list[NewsItem], date_label: str) -> str:
    lead = (items[0].title_zh or items[0].title) if items else "今日暂无重要更新"
    if len(lead) > 34:
        lead = lead[:33] + "…"
    return f"【刀塔世界日报】{lead}｜{date_label}"


def _item_html(item: NewsItem, index: int) -> str:
    corroboration = ""
    if item.corroborating_sources:
        corroboration = f'<div class="corroboration">交叉来源：{html.escape("、".join(item.corroborating_sources))}</div>'
    return f"""
<article class="news-card">
  <div class="news-index">{index:02d}</div>
  <div class="news-body">
    <div class="meta"><span class="tier tier-{html.escape(item.source_tier)}">{html.escape(source_label(item))}</span><span>{html.escape(item.source_name)}</span><span>{item.published_at.astimezone(DISPLAY_TZ).strftime('%m-%d %H:%M')}</span></div>
    <h3><a href="{html.escape(item.url, quote=True)}">{html.escape(item.title_zh or item.title)}</a></h3>
    <p>{html.escape(item.summary_zh or item.summary)}</p>
    <div class="why"><strong>为什么重要：</strong>{html.escape(item.why_it_matters)}</div>
    {corroboration}
  </div>
</article>""".strip()


def render_html(items: list[NewsItem], template_path: Path, generated_at: datetime, warnings: list[str]) -> tuple[str, str]:
    date_label = generated_at.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d")
    subject = subject_for(items, date_label)
    sections: OrderedDict[str, list[NewsItem]] = OrderedDict((name, []) for name in SECTION_ORDER)
    sections["今日重点"] = items[:3]
    for item in items[3:]:
        sections.setdefault(section_for(item), []).append(item)
    blocks: list[str] = []
    index = 1
    for section, section_items in sections.items():
        if not section_items:
            continue
        cards = []
        for item in section_items:
            cards.append(_item_html(item, index))
            index += 1
        blocks.append(f'<section><h2>{html.escape(section)}</h2>{"".join(cards)}</section>')
    if not blocks:
        blocks.append('<section class="empty"><h2>今日暂无重要更新</h2><p>采集流程已完成，但没有符合时间窗和质量阈值的条目。</p></section>')
    warning_html = ""
    if warnings:
        warning_html = '<div class="warnings"><strong>来源状态：</strong>' + html.escape("；".join(warnings)) + "</div>"
    template = Template(template_path.read_text(encoding="utf-8"))
    rendered = template.safe_substitute(
        subject=html.escape(subject),
        date_label=html.escape(date_label),
        generated_time=html.escape(generated_at.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d %H:%M %Z")),
        item_count=str(len(items)),
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
        lines.extend(
            [
                f"{index}. {item.title_zh or item.title}",
                f"   [{source_label(item)}] {item.source_name} · {item.published_at.astimezone(DISPLAY_TZ).strftime('%m-%d %H:%M')}",
                f"   {item.summary_zh or item.summary}",
                f"   为什么重要：{item.why_it_matters}",
                f"   原文：{item.url}",
                "",
            ]
        )
    if warnings:
        lines.extend(["来源状态：", *[f"- {warning}" for warning in warnings], ""])
    lines.append("本邮件只提供信息摘要，不构成投注或投资建议。")
    return subject, "\n".join(lines)
