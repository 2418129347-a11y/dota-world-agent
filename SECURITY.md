# Security Policy

## Supported version

Security fixes target the current `main` branch.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting flow from the repository's **Security** tab. Do not open a public Issue containing credentials, private email addresses, tokens, authorization codes, or exploit details.

Include:

- the affected file, workflow, or behavior;
- steps to reproduce without including live credentials;
- the potential impact;
- a suggested mitigation, if available.

## Secret handling

- Store SMTP credentials and API keys only in GitHub Actions Secrets or a trusted local secret store.
- Never commit `.env`, generated state, email artifacts, access tokens, or SMTP authorization codes.
- If a secret is exposed, revoke and rotate it first, then remove it from Git history before making the repository public again.
- Pull requests from forks do not receive repository secrets under the provided workflows.

## Untrusted content

Feed titles, summaries, match data, pages, and model inputs are treated as untrusted. They must not be interpreted as instructions, and they must remain bounded before being sent to an optional summarizer.
