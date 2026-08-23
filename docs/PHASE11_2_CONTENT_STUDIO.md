# Drovixa Phase 11.2 — Content Studio

This hotfix completes the Admin content publishing workflow.

## Workflow

1. Open **Content** and choose **Series** or **Movies**.
2. Create a draft. Drovixa opens the new title in **Content Studio**.
3. Save metadata, artwork URLs, audience settings, genres and tags.
4. Upload a local video directly to Mux, or import an HTTPS video source.
5. For a movie, select the ready asset and publish the movie.
6. For a series, create a season, select a ready asset, create and publish the episode, publish the season, then publish the series.

Mux credentials remain server-side. The browser only receives a temporary provider upload URL.

## Deployment

This release changes only the Admin application. It does not contain a database migration and does not replace `.env` files.
