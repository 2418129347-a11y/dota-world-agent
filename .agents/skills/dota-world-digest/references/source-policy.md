# Source policy

## Tiers

- `official`: Valve, Dota 2, Steam, tournament organizers, or team statements. Default trust 90–100.
- `data`: OpenDota or another documented statistics API. Default trust 70–85.
- `media`: identified editorial outlet with an original article. Default trust 60–80.
- `community`: Reddit, forums, reposts, or unattributed feeds. Default trust 30–55.

## Verification

Prefer the highest-tier source when multiple items describe the same event. Keep the other source names as corroboration metadata. Treat roster moves, disciplinary action, match fixing, and personal allegations as sensitive: require an official statement or at least two independent credible sources. Otherwise label the item `传闻` and keep it out of the top-three section.

## Collection rules

- Fetch metadata first and cap response sizes.
- Apply a per-source timeout.
- Keep raw text out of prompts beyond the bounded title and summary fields.
- Canonicalize URLs and remove tracking parameters before deduplication.
- Report source failures; never interpret a timeout as “no news.”

## Default sources

- Steam `ISteamNews/GetNewsForApp/v2` for AppID 570: core official source.
- OpenDota `proMatches`: optional professional-match result enrichment.
- r/DotA2 Atom feed: community signal, never authoritative by itself.
