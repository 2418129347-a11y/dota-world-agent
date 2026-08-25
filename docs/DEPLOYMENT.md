# GitHub Actions Deployment

## 1. Fork and enable Actions

Fork the repository, open the **Actions** tab, and enable workflows for the fork.

## 2. Configure Secrets

Open **Settings → Secrets and variables → Actions**.

For QQ SMTP, add repository Secrets:

- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `DIGEST_TO`

Optional Secrets:

- `OPENAI_API_KEY`
- `RESEND_API_KEY`
- `DIGEST_FROM`

Never store secret values in workflow YAML, README files, Issues, or Pull Requests.

## 3. Configure Variables

Add repository Variables:

- `ENABLE_SEND=true` to allow delivery;
- optional `OPENAI_MODEL`;
- optional `SMTP_HOST` and `SMTP_PORT`.

Keep `ENABLE_SEND` unset or `false` for a shadow run.

## 4. Test manually

Run **Daily Dota World Digest → Run workflow** without a date. Confirm the run report shows `delivery.sent: true` before relying on the schedule.

To backfill a calendar day, enter an Asia/Shanghai date such as `2026-08-16`. Dated runs do not update the normal seen-item state.

## 5. Schedule

The included workflow schedules 15-minute heartbeats across the nominal UTC window and the preceding three hours. A heartbeat arriving from 06:30 through 07:59 `Asia/Shanghai` waits in the cloud until 08:00; one arriving from 08:00 through 09:29 sends immediately; later scheduled runs are rejected. The first successful delivery records the local calendar day in cached state, so later heartbeats skip SMTP delivery. This mitigates missing and multi-hour-delayed cron events, but GitHub does not guarantee that a scheduled run will be created. The workflow runs in GitHub's cloud and does not require a local computer or Codex session.

Tier 1 event reminders are configured in `.agents/skills/dota-world-digest/references/tier1-events.json` and appear one day before the event. Update the official source links and exact bracket-stage entries when organizers publish or revise a schedule.

## Troubleshooting

- `SMTP_PASSWORD` failure: generate a new QQ SMTP authorization code; do not use the QQ account password.
- No email: check `ENABLE_SEND`, recipient Secret, spam folder, and the workflow report.
- Empty digest: inspect source warnings and the configured time window.
- Missing Chinese-player match: update `tracked_overseas_teams` in the editorial policy.
