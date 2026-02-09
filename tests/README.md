# tests

124 tests across 7 test modules. All tests use an in-memory SQLite database -- no network access or gateway required.

## Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `test_db.py` | ~30 | Database CRUD, retention cleanup, multi-site filtering, historical comparison, empty defaults |
| `test_api.py` | ~40 | REST endpoints, query param validation, health score calculation, Basic Auth, pagination |
| `test_alerts.py` | ~15 | Rule evaluation, cooldown enforcement, webhook delivery, metric extraction |
| `test_ws.py` | 5 | WebSocket connect/disconnect, broadcast, dead connection cleanup |
| `test_poller.py` | ~15 | Data parsing, safe type conversions, per-endpoint error isolation |
| `test_parser.py` | ~10 | NetFlow/IPFIX parsing, IP address conversion, protocol mapping |
| `test_export.py` | ~9 | CSV and JSON export for clients and WAN data |

## Fixtures (conftest.py)

| Fixture | Description |
|---------|-------------|
| `tmp_db` | Empty in-memory `Database` instance |
| `populated_db` | Database pre-loaded with sample data for query tests |
| `test_client` | FastAPI `TestClient` wired to the app with test DB |

## Running

```bash
# All tests
python3 -m pytest tests/ -v

# Single file
python3 -m pytest tests/test_api.py -v

# With coverage
python3 -m pytest tests/ --cov=unifi_monitor --cov-report=term-missing

# Via Makefile
make test
```

## CI

Tests run on Python 3.10, 3.11, and 3.12 in GitHub Actions (`.github/workflows/ci.yml`).

## Dependencies

Test dependencies are in `pyproject.toml` under `[project.optional-dependencies] dev`:

- `pytest>=8.0`
- `pytest-asyncio>=0.24`
- `ruff>=0.8`

Install with:

```bash
pip install -e ".[dev,netflow]"
```
