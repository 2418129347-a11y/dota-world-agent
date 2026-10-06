"""Clock, delivery checks and credential-free GitHub failure notifications."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, time as clock_time
from pathlib import Path
from zoneinfo import ZoneInfo


DISPLAY_TZ = ZoneInfo("Asia/Shanghai")
ALERT_MARKER = "<!-- dota-digest-delivery-alert -->"
ALERT_TITLE = "[DOTA 日报] 自动发送异常"


def seconds_until_delivery(now: datetime, event: str) -> int:
    if event != "schedule":
        return 0
    local = now.astimezone(DISPLAY_TZ)
    target = datetime.combine(local.date(), clock_time(8), tzinfo=DISPLAY_TZ)
    return max(0, int((target - local).total_seconds()))


def delivery_health(report_path: Path, state_path: Path, enabled: str) -> tuple[bool, str]:
    if enabled != "true":
        return False, "sending_disabled"
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        delivery = report["delivery"]
        day = report["delivery_date"]
        if delivery.get("sent") is True and delivery.get("requested") is True:
            return True, "sent"
        if delivery.get("reason") == "already_sent_today":
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if day in state.get("sent_dates", []):
                return True, "already_sent_today_verified"
        return False, str(delivery.get("reason") or "not_sent")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False, "missing_or_invalid_delivery_report"


def sync_alert(api, healthy: bool, reason: str, run_url: str) -> None:
    # Exact marker, bot identity and title keep unrelated user issues untouched.
    issues = []
    page = 1
    while True:
        batch = api("GET", f"/issues?state=open&per_page=100&page={page}")
        issues.extend(issue for issue in batch if (
            not issue.get("pull_request")
            and issue.get("title") == ALERT_TITLE
            and ALERT_MARKER in (issue.get("body") or "")
            and issue.get("user", {}).get("login") == "github-actions[bot]"
        ))
        if len(batch) < 100:
            break
        page += 1
    if healthy:
        for issue in issues:
            api("POST", f"/issues/{issue['number']}/comments", {
                "body": f"已核验恢复发送。运行记录：{run_url}"
            })
            api("PATCH", f"/issues/{issue['number']}", {"state": "closed"})
        return
    # Do not put report bodies, SMTP exception text, recipients or secrets here.
    body = (
        f"{ALERT_MARKER}\n日报发送未通过核验。\n\n"
        f"原因代码：`{reason}`\n\n运行记录：{run_url}\n\n"
        "请核查工作流日志和邮箱配置；传输结果不确定时，先确认收件情况再解除阻止。"
    )
    if issues:
        api("PATCH", f"/issues/{issues[0]['number']}", {"body": body})
        # Comments trigger GitHub notifications for subsequent failures too.
        api("POST", f"/issues/{issues[0]['number']}/comments", {"body": body})
    else:
        api("POST", "/issues", {"title": ALERT_TITLE, "body": body})


def github_api(method: str, path: str, body=None):
    repo = os.environ["GITHUB_REPOSITORY"]
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={
            "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "DotaWorldDigest/0.1",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("gate", "health", "notify"))
    args = parser.parse_args(argv)
    if args.command == "gate":
        wait = seconds_until_delivery(datetime.now(DISPLAY_TZ), os.environ.get("GITHUB_EVENT_NAME", ""))
        if wait:
            print(f"Waiting {wait}s until Beijing 08:00", flush=True)
            time.sleep(wait)
        print("Beijing execution time: " + datetime.now(DISPLAY_TZ).isoformat())
        return 0
    if args.command == "health":
        healthy, reason = delivery_health(Path("output/report.json"), Path("state/seen.json"), os.environ.get("ENABLE_SEND", ""))
        if os.environ.get("PRIOR_STATUS", "success") != "success" and healthy:
            healthy, reason = False, "workflow_step_failed"
        output = f"delivery_ok={str(healthy).lower()}\nreason={reason}\n"
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            handle.write(output)
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(f"日报投递核验：{'通过' if healthy else '失败'}（{reason}）\n")
        print(output.strip())
        return 0 if healthy else 1
    healthy = (
        os.environ.get("DELIVERY_OK") == "true"
        and os.environ.get("DIGEST_RESULT") == "success"
        and os.environ.get("GATE_RESULT") == "success"
    )
    reason = os.environ.get("DELIVERY_REASON") or "workflow_did_not_complete"
    run_url = f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    try:
        sync_alert(github_api, healthy, reason, run_url)
    except Exception as exc:
        # Preserve the failed digest job; never replace its cause with alert details.
        print(f"::error::GitHub notification failed ({type(exc).__name__}); original delivery result remains unchanged.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
