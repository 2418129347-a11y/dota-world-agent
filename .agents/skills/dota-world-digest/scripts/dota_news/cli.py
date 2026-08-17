from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .collectors import collect_all
from .editorial import compose_digest, enrich_match_reports, merge_match_series
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


def _load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("seen", []))
    except (OSError, ValueError):
        return set()


def _write_seen(path: Path, previous: set[str], items: list[NewsItem]) -> None:
    values = set(previous)
    for item in items:
        values.add(item.item_id)
        values.add(canonical_url(item.url))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"seen": sorted(values)[-2000:]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect and render a daily Dota 2 news digest.")
    parser.add_argument("--config", type=Path, default=SKILL_ROOT / "references" / "sources.json")
    parser.add_argument("--fixture", type=Path, help="Use local fixture items instead of network collectors.")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--state-file", type=Path, default=Path("state/seen.json"))
    parser.add_argument("--hours", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--summarizer", choices=("auto", "fallback", "openai"), default="auto")
    parser.add_argument("--send", action="store_true", help="Send through the configured SMTP or Resend provider after rendering.")
    parser.add_argument("--write-state", action="store_true")
    parser.add_argument("--ignore-seen", action="store_true")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    now = datetime.now(timezone.utc)
    config = _load_json(args.config)
    policy_path = SKILL_ROOT / "references" / "editorial-policy.json"
    editorial_policy = _load_json(policy_path)
    ranking = dict(config.get("ranking", {}))
    if args.hours is not None:
        ranking["hours"] = args.hours
    if args.limit is not None:
        ranking["limit"] = args.limit
    warnings: list[str] = []
    if args.fixture:
        collected = _load_fixture(args.fixture)
    else:
        collected, collector_warnings = collect_all(config, now)
        warnings.extend(collector_warnings)
    collected = merge_match_series(collected, editorial_policy)
    seen = set() if args.ignore_seen else _load_seen(args.state_file)
    selected = select_items(collected, ranking, seen, now, editorial_policy)
    selected = compose_digest(selected, editorial_policy)
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
    if args.send:
        response = send_email(subject, html_body, text_body, now.astimezone(DISPLAY_TZ).date())
        delivery = {
            "requested": True,
            "sent": True,
            "provider": response.get("provider"),
            "provider_id": response.get("id"),
        }
    if args.write_state:
        _write_seen(args.state_file, seen, selected)
    report = {
        "generated_at": now.isoformat(),
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
