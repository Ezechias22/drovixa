# Phase 9 validation record

Phase 9 was validated before packaging with checks that do not require Drovixa
production credentials:

- Python syntax compilation for the backend, migrations, and tests.
- JSON parsing for all workspace package manifests, Expo configuration, EAS
  profiles, and the npm lockfile.
- YAML parsing for local Compose, production Compose, and `render.yaml`.
- Node syntax validation for `mobile/app.config.js`.
- TypeScript checks for the Web and Admin applications.
- Static secret scan excluding examples and documentation.
- Archive inspection that rejects `.env`, Firebase credential files,
  `node_modules`, build output, and local caches.

The mobile TypeScript check requires the new `expo-device` and
`expo-notifications` dependencies. Run `npm install` after extracting the ZIP,
then run:

```powershell
npm run typecheck --workspace @drovixa/mobile
npm run typecheck --workspace @drovixa/web
npm run typecheck --workspace @drovixa/admin
```

Firebase delivery itself must be tested with the owner's Firebase project,
server credential, and a physical Android device running an EAS development or
production build. Render provisioning likewise requires the owner's Render
account, connected Git repository, Mux secrets, Firebase secrets, and final
allowed origins.
