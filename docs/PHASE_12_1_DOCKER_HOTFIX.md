# Drovixa Phase 12.1 — Docker wheel hotfix

This hotfix replaces the backend multi-stage wheel build with a direct,
validated dependency installation in the runtime image. It fixes Docker Desktop
builds that report `COPY --from=builder /wheels /wheels: "/wheels": not found`.

The image still runs as the unprivileged `drovixa` user and now executes
`python -m pip check` during the build. It also updates the image release label
to `0.12.0`.

The overlay changes only `backend/Dockerfile`. It does not modify `.env`, local
or Neon databases, Redis data, Mux, Firebase, Web, Admin, or Mobile source.
