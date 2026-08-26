# Drovixa Phase 12.2 — pinned Python runtime hotfix

This hotfix pins the backend to the previously validated Python 3.12 slim image
digest used by Drovixa and makes the Docker build fail immediately unless all
runtime dependencies are really installed.

The build now verifies that `requirements.txt` is present, Python 3.12 executes,
pip is bootstrapped in isolated mode, package dependencies are consistent, and
the `alembic` and `celery` executables plus critical Python imports exist.

This overlay changes only `backend/Dockerfile`. It does not modify any database,
volume, `.env`, Mux, Firebase, Mobile, Web, or Admin data.
