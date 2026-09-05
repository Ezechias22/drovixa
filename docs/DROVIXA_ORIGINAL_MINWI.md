# Drovixa Original: Minwi nan Jakmèl

`Minwi nan Jakmèl` is a normal published Drovixa Original series, not showcase or demo content.

- Format: vertical 9:16
- Season 1: ongoing
- Episode 1: `Siyal Minwi a`
- Runtime: 2 minutes 1 second
- Access: free
- Catalog metadata: Haitian Creole, French, English, Spanish, and Brazilian Portuguese
- Playback: bundled HLS served by the Drovixa API

At API startup, `python -m app.scripts.original_catalog sync` removes only records tagged
with the former `showcase-v1` batch and publishes this production idempotently.
Owner-created content is not selected or deleted by that cleanup.
