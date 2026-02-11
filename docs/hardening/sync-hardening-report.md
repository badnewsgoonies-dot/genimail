# Sync Hardening Report

Date: 2026-02-10

## Implemented in this pass

1. Worker callback exception routing to error handler (`genimail_qt/helpers/worker_manager.py`).
2. Poll lock race removal and generation-based stale callback protection (`genimail_qt/mixins/auth.py`, `genimail_qt/window.py`).
3. Dedicated delta-init error callback path (`genimail_qt/mixins/auth.py`).
4. Delta-410 stale token reset and re-initialization flow (`genimail/services/mail_sync.py`, `genimail/infra/cache_store.py`).
5. Graph JSON parse guards (`genimail/infra/graph_client.py`).
6. Graph HTTP 429 retry/backoff with `Retry-After` support (`genimail/infra/graph_client.py`).
7. Delta pagination cycle and max-page guards (`genimail/infra/graph_client.py`).
8. SQLite connection hardening: timeout, FK pragma, WAL+synchronous mode, quick integrity check (`genimail/infra/cache_store.py`).
9. Migration flow now transaction-wrapped and version-stepped (`genimail/infra/cache_store.py`).
10. Multi-statement writes wrapped in atomic transactions (`genimail/infra/cache_store.py`).
11. Session/connection lifecycle cleanup via `close()` hooks (`genimail/infra/graph_client.py`, `genimail/infra/cache_store.py`, `genimail_qt/mixins/window_state.py`).
12. Default cache search limit to prevent unbounded queries (`genimail/infra/cache_store.py`).

## Validation

- Full test suite passing: `174 passed`.
- New/updated tests cover:
  - 429 retry and JSON parse failures.
  - Delta-expiry recovery behavior.
  - Poll generation and in-flight reset behavior.
  - Worker callback exception routing.
  - Delta link clearing and cache close lifecycle.
  - Default search-limit behavior.
