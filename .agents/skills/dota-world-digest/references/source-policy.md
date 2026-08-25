# Source policy

## Tiers

- `official`: Valve, Dota 2, Steam, tournament organizers, or team statements. Default trust 90–100.
- `data`: OpenDota or another documented statistics API. Default trust 70–85.
- `media`: identified editorial outlet with an original article. Default trust 60–80.
- `community`: Reddit, forums, reposts, or unattributed feeds. Default trust 30–55.

## Verification

Prefer the highest-tier source when multiple items describe the same event. Keep the other source names as corroboration metadata. Treat disciplinary action, match fixing, and personal allegations as sensitive: require an official statement or at least two independent credible sources. An allowlisted direct link to a team or organizer account confirms only the sanction and wording visible in that announcement; it does not validate adjacent community claims. Otherwise exclude the item from the email.

Tier 1 reminders require a dated calendar entry with at least one organizer or official event source and a `verified_at` date. A displayed fixture additionally requires `scheduled_at`, both teams, stage, best-of format, elimination status, `verified_at`, and a direct schedule source. If any required fixture field is missing, show that exact pairings are pending rather than guessing. Advancement, lower-bracket, and elimination claims require an exact series snapshot with tournament, both teams, scheduled date, bracket stage, `loser_out`, `verified_at`, and at least two schedule sources. Article prose cannot substitute for the stage snapshot.

## Circle-news ranking

Only the configured interests in `editorial-policy.json` are eligible. Rank them using credibility 30%, China relevance 25%, impact 20%, recency 10%, personal-interest match 10%, and heat/corroboration 5%. Priority order is Chinese roster/player news, Tier 1 global player movement, then the remaining eligible categories. Post-TI transfers, departures, retirements, disbands, and rebuilds involving the configured elite teams or players are Tier 1 intelligence. Normally require source trust of at least 65. A community rumor may use the configured 48-hour window and bypass the normal trust floor only when it directly matches an eligible movement category and simultaneously meets that category's upvote and comment thresholds. Show engagement counts and label it as unconfirmed. Quality wins over filling the quota.

## Collection rules

- Fetch metadata first and cap response sizes.
- Apply a per-source timeout.
- Keep raw text out of prompts beyond the bounded title and summary fields.
- Canonicalize URLs and remove tracking parameters before deduplication.
- Report source failures; never interpret a timeout as “no news.”

## Default sources

- Steam `ISteamNews/GetNewsForApp/v2` for AppID 570: core official source.
- OpenDota `proMatches` and match details: professional series grouping, player/hero statistics, and data-backed commentary. Team/player coverage is bounded by the public list plus the configurable watchlists.
- A bounded two-day r/DotA2 index plus Reddit public embed metadata: discover China-related and Tier 1 movement posts, read the live upvote display, and count indexed comments up to the configured cap. High-heat post-TI shuffle hubs may contribute a bounded set of top-team/player comment signals; those snippets remain community rumors and never become facts through popularity alone. High-engagement posts that link directly to explicitly allowlisted team or organizer accounts may be retained as official-reference discoveries; only the official action is confirmed. The index has no uptime guarantee; if discovery or either engagement lookup fails, omit the item rather than guessing.
- Google News Dota 2 RSS: discovery only, restricted to the publisher allowlist; display and score the underlying publisher rather than Google News.
