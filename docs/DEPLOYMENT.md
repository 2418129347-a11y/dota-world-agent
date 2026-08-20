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

The included workflow uses UTC cron entries equivalent to 08:23, 08:38, and 08:53 in `Asia/Shanghai`. The first successful delivery records the local calendar day in the cached state, so later backup runs skip SMTP delivery. Scheduled GitHub Actions can still be delayed by platform load. They run in GitHub's cloud and do not require a local computer or Codex session.

## Troubleshooting

- `SMTP_PASSWORD` failure: generate a new QQ SMTP authorization code; do not use the QQ account password.
- No email: check `ENABLE_SEND`, recipient Secret, spam folder, and the workflow report.
- Empty digest: inspect source warnings and the configured time window.
- Missing Chinese-player match: update `tracked_overseas_teams` in the editorial policy.
