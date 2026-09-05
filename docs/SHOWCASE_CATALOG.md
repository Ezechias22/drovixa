# Drovixa showcase catalog

This release includes a removable demonstration catalog identified by the exact batch key
`showcase-v1`. It contains 15 original fictional series, two free 12-second HLS demo episodes
per series, and localized series and episode metadata in English, French, Brazilian Portuguese,
Spanish, and Haitian Creole.

The artwork and video clips in `backend/app/demo_media` were created specifically for this
repository. They do not copy third-party movies, series, posters, trailers, or trademarks.

## Install or refresh

Run migrations first, then install the catalog:

```powershell
Set-Location ".\backend"
alembic upgrade head
python -m app.scripts.demo_catalog install
```

Render runs `python -m app.scripts.demo_catalog sync` after migrations. The API service in
`render.yaml` has `DEMO_CATALOG_ENABLED=true`, so the first deployment installs the catalog and
later deployments update it idempotently.

## Remove before adding real content

Change the API service variable `DEMO_CATALOG_ENABLED` to `false`, then redeploy. The same sync
command removes only rows with `demo_batch=showcase-v1` and their bundled demo video assets. It
does not remove administrator-created content.

For a one-time manual removal:

```powershell
Set-Location ".\backend"
python -m app.scripts.demo_catalog remove
```

## Language behavior

Mobile requests send `X-Drovixa-Language` from the language selected in the app. The API accepts
`en`, `fr`, `pt-BR`, `es`, and `ht`; it also understands matching `Accept-Language` values and
falls back to English.
