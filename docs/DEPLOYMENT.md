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

The workflow uses four Beijing triggers: 07:43 `Asia/Shanghai` waits until 08:00, with fallbacks at 08:17, 09:17 and 16:19. Delayed scheduled runs send on the actual Beijing calendar day, without a morning cutoff. Successful delivery records the date in cached state; later triggers and ordinary manual runs skip that date. Explicit historical-date runs remain separate. GitHub does not guarantee punctual execution or creation of a scheduled run; if all triggers are missing, this workflow cannot alert independently. It runs in the cloud without a local computer or Codex session.

The delivery-health step checks `output/report.json` and `state/seen.json`. Only a confirmed send or a verified already-sent date passes. `ENABLE_SEND` must be true in this production workflow: disabled sending, missing reports and SMTP failures are errors. A separate job with `issues: write` permission creates or updates one bot-owned failure Issue and closes it after verified recovery. GitHub account notification preferences govern email alerts; no SMTP credential is used in the notification job. Notification failures remain separate and do not overwrite the failed delivery job.

SMTP connection or login disconnects retry up to three times. Once transmission starts, failures produce a persisted `uncertain_dates` entry, blocking further automatic sends on that date even in later heartbeats. After checking the recipient inbox, a maintainer can remove the block (or mark the day sent if delivery is confirmed). State is explicitly saved even when SMTP fails. Cache loss can still weaken duplicate protection; never assume SMTP guarantees exactly-once delivery.

Tier 1 event reminders are configured in `.agents/skills/dota-world-digest/references/tier1-events.json` and appear one day before the event. Update the official source links and exact bracket-stage entries when organizers publish or revise a schedule.

## Troubleshooting

- `SMTP_PASSWORD` failure: generate a new QQ SMTP authorization code; do not use the QQ account password.
- No email: check `ENABLE_SEND`, recipient Secret, spam folder, and the workflow report.
- Empty digest: inspect source warnings and the configured time window.
- Missing Chinese-player match: update the source-linked `current_player_affiliations` snapshot in the editorial policy. Do not reuse a historical team after the player transfers.
