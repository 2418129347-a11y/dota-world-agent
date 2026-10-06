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

- `DEEPSEEK_API_KEY` for rich Chinese recaps and intelligence (never paste it into chat or repository files)
- `RESEND_API_KEY`
- `DIGEST_FROM`

Never store secret values in workflow YAML, README files, Issues, or Pull Requests.

## 3. Configure Variables

Add repository Variables:

- `ENABLE_SEND=true` to allow delivery;
- optional `DEEPSEEK_MODEL` (default `deepseek-flash`);
- optional `SMTP_HOST` and `SMTP_PORT`.

Keep `ENABLE_SEND` unset or `false` for a shadow run.

## 4. Test manually

Run **Daily Dota World Digest → Run workflow** without a date. Confirm the run report shows `delivery.sent: true` before relying on the schedule.

For content verification, select `preview=true`: no SMTP transmission, no delivery/seen-state writes, no delivery failure Issue changes. Preview artifacts contain both email formats and the run report. Confirm `summarizer: deepseek`, paragraph evidence, and model usage before enabling upgraded content. Keep preview disabled for real scheduled sends.

Select `preview_fixture=true` together with `preview=true` for the three clearly fictional layout/evidence samples in `tests/fixtures/editorial_items.json`. This option is ignored in production delivery. Use it to verify the API even when today's real sources contain no eligible news; fictional samples never belong in a real email.

DeepSeek uses its official Chat Completions endpoint, non-thinking mode, JSON Output, up to five requests per run, 45-second timeouts and 6,000 output tokens per request. Requests are not retried automatically. Missing keys, insufficient balance, API failures or invalid content cause a visible short-summary fallback, never a GPT request. API charges are independent of any web-chat subscription. The `openai` CLI mode has been removed; migrate to `deepseek` or `auto`.

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
- Brief or missing intelligence: inspect `content_status`, `omitted_content_ids`, article/discussion failures and `summary_usage`. Source links without substantive prose are deliberately omitted. JSON validation and valid citations are not a complete semantic fact check.
- Missing Chinese-player match: update the source-linked `current_player_affiliations` snapshot in the editorial policy. Do not reuse a historical team after the player transfers.
