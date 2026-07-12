# CLI Reference

`eahelper` is a single entry point with five subcommands. Every subcommand accepts a `--help` flag
for authoritative, version-specific detail — treat this file as a summary, and defer to
`eahelper <subcommand> --help` when flags don't match what you see here.

```
eahelper <subcommand> [OPTIONS]
```

| Subcommand | Description |
|---|---|
| `proxy`    | Start the local GraphQL proxy + GraphiQL UI, authenticated via browser CDP or API key |
| `diagnose` | Test DNS → TCP → TLS → HTTP connectivity and recommend an SSL fix |
| `download` | Download factsheets/relationships from LeanIX (via the proxy) to local JSON |
| `load`     | Load previously downloaded JSON into KuzuDB or Neo4j |
| `seed`     | Load a small built-in demo graph, no LeanIX access needed |

## Shared SSL flags (available on `proxy`, `diagnose`, `download`)

| Flag | Default | Description |
|---|---|---|
| `--ca-bundle PATH` | none | Custom PEM CA bundle (corporate SSL-inspection proxy) |
| `--no-verify-ssl` | off | Disable TLS verification entirely (insecure — testing only) |
| `--legacy-ssl` | off | Relax strict X.509 validation — fixes MITM proxy certs missing `Authority Key Identifier` |

## `eahelper proxy`

| Flag | Default | Description |
|---|---|---|
| `--url URL` | prompted if omitted | LeanIX workspace base URL, e.g. `https://eu-10.leanix.net/YourWorkspace` |
| `--port PORT` | `8765` | Local server port |
| `--connect CDP_URL` | `http://localhost:9222` | Chrome DevTools Protocol endpoint |
| `--token TOKEN` | none | Use this Bearer token directly — skips browser extraction |
| `--api-token KEY` | none (env: `LEANIX_API_TOKEN`) | LeanIX Technical User API key — OAuth2 exchange, no browser needed |
| `--no-save` | off | Don't persist the extracted token to disk |

```bash
eahelper proxy
eahelper proxy --url https://eu-10.leanix.net/MyWorkspace
eahelper proxy --api-token "your-api-key-here"
eahelper proxy --token "eyJhbGci..."
eahelper proxy --port 9000
eahelper proxy --legacy-ssl
```

### Runtime endpoints (while `proxy` is running)

| Method | Path | Description |
|---|---|---|
| GET  | `/graphql` | GraphiQL interactive UI |
| POST | `/graphql` | GraphQL proxy to LeanIX |
| GET  | `/health` | Health check + upstream URL |
| GET  | `/token` | Show masked current Bearer token |
| POST | `/token` | Replace the Bearer token at runtime |
| POST | `/token/refresh` | Force re-extraction from the connected browser |

```bash
curl http://localhost:8765/health
curl -X POST http://localhost:8765/token -H "Content-Type: application/json" \
  -d '{"token": "eyJhbGci..."}'
curl -X POST http://localhost:8765/token/refresh
```

```powershell
Invoke-RestMethod http://localhost:8765/health
Invoke-RestMethod -Uri http://localhost:8765/token -Method POST `
  -ContentType "application/json" -Body '{"token": "eyJhbGci..."}'
Invoke-RestMethod -Uri http://localhost:8765/token/refresh -Method POST
```

## `eahelper diagnose`

```bash
eahelper diagnose
eahelper diagnose --url https://eu-10.leanix.net/MyWorkspace
```

Runs DNS → TCP → raw TLS → system-CA TLS → legacy-mode TLS → httpx checks in sequence and prints a
recommended fix command at the end (usually `--legacy-ssl` for corporate MITM proxies).

## `eahelper download`

| Flag | Default | Description |
|---|---|---|
| `--type`, `-t TYPE` | none (all mapped types) | FactSheet type, e.g. `Application` |
| `--subtype`, `-s NAME` | none | Filter by category/subtype (repeatable) |
| `--proxy URL` | `http://localhost:8765/graphql` | GraphQL proxy URL — the `proxy` subcommand must already be running |
| `--output`, `-o PATH` | stdout / `data/leanix/` | Output file or directory |
| `--format`, `-f` | `json` | `json` or `csv` |
| `--list-types` | off | List all FactSheet types in the workspace and exit |
| `--list-subtypes` | off | List subtypes/categories for `--type` and exit |
| `--list-relations` | off | List relation fields for `--type` and exit |
| `--limit`, `-n N` | none | Cap records per type — use for a fast smoke test |
| `--all-factsheets` | off | Bypass any mapping whitelist; discover and download every type live |

```bash
eahelper download --list-types
eahelper download --type Application --output apps.json
eahelper download --type Application --limit 10 --output sample.json
eahelper download --type Application --subtype "Business Application" --format csv -o apps.csv
eahelper download --all-factsheets --output data/leanix/
```

## `eahelper load`

| Flag | Default | Description |
|---|---|---|
| `--db {kuzu,neo4j}` | prompted if omitted | Target graph database |
| `--data-dir PATH` | `data/leanix` | Directory of previously downloaded JSON |
| `--mapping PATH` | `metamodel-mapping.yaml` in CWD, else bundled default | Controls which types/relations are loaded and how they're named |
| `--limit N` | none | Cap rows loaded per type/relation — smoke test |
| `--skip-download` | n/a | (If load also triggers a download step) load only from existing JSON |

```bash
eahelper load --db kuzu
eahelper load --db neo4j
eahelper load --db kuzu --limit 10
eahelper load --db kuzu --mapping path/to/my-mapping.yaml
```

If `--db` is omitted, you'll be prompted interactively. Default to `kuzu` unless the user has an
existing Neo4j server or explicitly wants Neo4j.

## `eahelper seed`

```bash
eahelper seed --db kuzu
eahelper seed --db neo4j
```

Clears the target database and loads a small built-in demo graph (~8 applications, 6 business
capabilities, 11 interfaces) — useful for verifying the DB setup or trying queries without any
LeanIX access.

## Typical end-to-end sequence

```bash
eahelper proxy &                 # terminal 1 — leave running
eahelper download                # terminal 2
eahelper load --db kuzu          # terminal 2
```

```powershell
# Terminal 1
eahelper proxy
# Terminal 2 (after proxy is up)
eahelper download
eahelper load --db kuzu
```
