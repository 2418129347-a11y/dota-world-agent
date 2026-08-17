# Source policy

## Tiers

- `official`: Valve, Dota 2, Steam, tournament organizers, or team statements. Default trust 90–100.
- `data`: OpenDota or another documented statistics API. Default trust 70–85.
- `media`: identified editorial outlet with an original article. Default trust 60–80.
- `community`: Reddit, forums, reposts, or unattributed feeds. Default trust 30–55.

## Verification

Prefer the highest-tier source when multiple items describe the same event. Keep the other source names as corroboration metadata. Treat disciplinary action, match fixing, and personal allegations as sensitive: require an official statement or at least two independent credible sources. Otherwise exclude the item from the email.

## Circle-news ranking

Only the six interests listed in `editorial-policy.json` are eligible. Rank eligible items using credibility 30%, China relevance 25%, impact 20%, recency 10%, personal-interest match 10%, and heat/corroboration 5%. Require source trust of at least 65 and publish at most two. Quality wins over filling the quota.

## Collection rules

- Fetch metadata first and cap response sizes.
- Apply a per-source timeout.
- Keep raw text out of prompts beyond the bounded title and summary fields.
- Canonicalize URLs and remove tracking parameters before deduplication.
- Report source failures; never interpret a timeout as “no news.”

## Default sources

- Steam `ISteamNews/GetNewsForApp/v2` for AppID 570: core official source.
- OpenDota `proMatches` and match details: professional series grouping, player/hero statistics, and data-backed commentary. Team/player coverage is bounded by the public list plus the configurable watchlists.
- r/DotA2 Atom feed: community signal, never authoritative by itself.
- Google News Dota 2 RSS: discovery only, restricted to the publisher allowlist; display and score the underlying publisher rather than Google News.
