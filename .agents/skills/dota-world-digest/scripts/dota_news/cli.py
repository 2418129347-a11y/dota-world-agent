from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .collectors import collect_all
from .editorial import apply_external_match_impacts, compose_digest, enrich_match_reports, merge_match_series
from .mailer import send_email
from .models import NewsItem
from .pipeline import select_items
from .render import render_html, render_text
from .summarizers import summarize
from .utils import canonical_url


SKILL_ROOT = Path(__file__).resolve().parents[2]
DISPLAY_TZ = ZoneInfo("Asia/Shanghai")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_fixture(path: Path) -> list[NewsItem]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [NewsItem.from_dict(item) for item in data]


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {"seen": [], "sent_dates": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"seen": [], "sent_dates": []}
    except (OSError, ValueError):
        return {"seen": [], "sent_dates": []}


def _write_state(
    path: Path,
    previous: set[str],
    sent_dates: set[str],
    items: list[NewsItem],
    delivered_date: str | None = None,
) -> None:
    values = set(previous)
    for item in items:
        values.add(item.item_id)
        values.add(canonical_url(item.url))
    if delivered_date:
        sent_dates.add(delivered_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"seen": sorted(values)[-2000:], "sent_dates": sorted(sent_dates)[-90:]},
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def filter_report_date(items: list[NewsItem], target_date: date) -> list[NewsItem]:
    return [item for item in items if item.published_at.astimezone(DISPLAY_TZ).date() == target_date]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect and render a daily Dota 2 news digest.")
    parser.add_argument("--config", type=Path, default=SKILL_ROOT / "references" / "sources.json")
    parser.add_argument("--fixture", type=Path, help="Use local fixture items instead of network collectors.")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--state-file", type=Path, default=Path("state/seen.json"))
    parser.add_argument("--hours", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--date", type=date.fromisoformat, help="Generate one Asia/Shanghai calendar day (YYYY-MM-DD).")
    parser.add_argument("--summarizer", choices=("auto", "fallback", "openai"), default="auto")
    parser.add_argument("--send", action="store_true", help="Send through the configured SMTP or Resend provider after rendering.")
    parser.add_argument("--write-state", action="store_true")
    parser.add_argument("--ignore-seen", action="store_true")
    parser.add_argument("--skip-if-sent-today", action="store_true", help="Skip delivery when state records a successful send for the current Asia/Shanghai day.")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target_date = args.date
    now = (
        datetime.combine(target_date, time.max, tzinfo=DISPLAY_TZ).astimezone(timezone.utc)
        if target_date
        else datetime.now(timezone.utc)
    )
    config = _load_json(args.config)
    policy_path = SKILL_ROOT / "references" / "editorial-policy.json"
    editorial_policy = _load_json(policy_path)
    ranking = dict(config.get("ranking", {}))
    if args.hours is not None:
        ranking["hours"] = args.hours
    elif target_date:
        ranking["hours"] = 24
    if args.limit is not None:
        ranking["limit"] = args.limit
    warnings: list[str] = []
    if args.fixture:
        collected = _load_fixture(args.fixture)
    else:
        collected, collector_warnings = collect_all(config, now)
        warnings.extend(collector_warnings)
    if target_date:
        collected = filter_report_date(collected, target_date)
    collected = merge_match_series(collected, editorial_policy)
    state = _load_state(args.state_file)
    seen = set() if args.ignore_seen else set(state.get("seen", []))
    sent_dates = set(state.get("sent_dates", []))
    selected = select_items(collected, ranking, seen, now, editorial_policy)
    selected = compose_digest(selected, editorial_policy)
    apply_external_match_impacts(selected, collected)
    if not args.fixture:
        warnings.extend(enrich_match_reports(selected))
    selected, summarizer_mode, summary_warnings = summarize(selected, args.summarizer)
    warnings.extend(summary_warnings)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = now.astimezone(DISPLAY_TZ).strftime("%Y-%m-%d")
    html_path = args.output_dir / f"dota-world-digest-{stamp}.html"
    text_path = args.output_dir / f"dota-world-digest-{stamp}.txt"
    report_path = args.output_dir / "report.json"
    subject, html_body = render_html(selected, SKILL_ROOT / "assets" / "digest.html", now, warnings)
    _, text_body = render_text(selected, now, warnings)
    html_path.write_text(html_body, encoding="utf-8")
    text_path.write_text(text_body, encoding="utf-8")
    delivery: dict = {"requested": args.send, "sent": False}
    delivery_date = now.astimezone(DISPLAY_TZ).date().isoformat()
    if args.send:
        if args.skip_if_sent_today and delivery_date in sent_dates:
            delivery = {"requested": True, "sent": False, "skipped": True, "reason": "already_sent_today"}
        else:
            response = send_email(subject, html_body, text_body, now.astimezone(DISPLAY_TZ).date())
            delivery = {
                "requested": True,
                "sent": True,
                "provider": response.get("provider"),
                "provider_id": response.get("id"),
            }
    if args.write_state:
        _write_state(
            args.state_file,
            seen,
            sent_dates,
            [] if delivery.get("skipped") else selected,
            delivery_date if delivery.get("sent") else None,
        )
    report = {
        "generated_at": now.isoformat(),
        "report_date": target_date.isoformat() if target_date else stamp,
        "subject": subject,
        "collected_count": len(collected),
        "selected_count": len(selected),
        "summarizer": summarizer_mode,
        "warnings": warnings,
        "delivery": delivery,
        "outputs": {"html": str(html_path), "text": str(text_path)},
        "items": [item.to_dict() for item in selected],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("subject", "collected_count", "selected_count", "summarizer", "warnings", "delivery", "outputs")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(run())
