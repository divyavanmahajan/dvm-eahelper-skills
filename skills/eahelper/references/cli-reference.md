# CLI Reference

`eahelper` is a single entry point with several subcommands. Every subcommand accepts a `--help`
flag for authoritative, version-specific detail — treat this file as a summary, and defer to
`eahelper <subcommand> --help` when flags don't match what you see here.

```
eahelper <subcommand> [OPTIONS]
```

| Subcommand | Description |
|---|---|
| `server`     | Run the supervisor: GraphQL proxy + embedded MCP endpoint + managed debug browser. `server start\|stop\|status` manage it as a background daemon |
| `diagnose`   | Test DNS → TCP → TLS → HTTP connectivity and recommend an SSL fix |
| `download`   | Download factsheets/relationships from LeanIX (via the proxy) to local JSON |
| `load`       | Load previously downloaded JSON into KuzuDB or Neo4j |
| `seed`       | Load a small built-in demo graph, no LeanIX access needed |
| `config`     | Show, set, or unset persisted settings in `~/.eahelper/config.toml` |
| `mcp`        | Run the MCP server over stdio transport |
| `mcp-config` | Print or install MCP client config for Claude Code / VS Code (Copilot) |

## Shared SSL flags (available on `server`, `diagnose`, `download`)

| Flag | Default | Description |
|---|---|---|
| `--ca-bundle PATH` | none | Custom PEM CA bundle (corporate SSL-inspection proxy) |
| `--no-verify-ssl` | off | Disable TLS verification entirely (insecure — testing only) |
| `--legacy-ssl` | off | Relax strict X.509 validation — fixes MITM proxy certs missing `Authority Key Identifier` |

## `eahelper server`

Runs the integrated supervisor: GraphQL proxy, embedded MCP endpoint (streamable HTTP at
`/mcp`), and a managed debug browser used only when a LeanIX token must be (re)captured.

| Flag | Default | Description |
|---|---|---|
| `--url URL` | prompted if omitted, then saved to `config.toml` | LeanIX workspace base URL, e.g. `https://eu-10.leanix.net/YourWorkspace` |
| `--port PORT` | `8765` | Local server port (serves GraphQL proxy + `/mcp`) |
| `--cdp-port PORT` | `19222` | Chrome DevTools Protocol port for the managed debug browser |
| `--browser {chrome,edge}` | platform default | Which browser the managed instance uses |
| `--keep-browser` | off | Don't auto-close the managed browser after a token is captured (equivalent to config `keep_open = true`) |
| `--token TOKEN` | none | Use this Bearer token directly — skips browser capture |
| `--api-token KEY` | none (env: `LEANIX_API_TOKEN`) | LeanIX Technical User API key — OAuth2 exchange, no browser needed |
| `--no-save` | off | Don't persist the extracted token to disk |
| `--mcp-read-only` | off | Restrict the embedded MCP `query` tool to read-only Cypher |

`server` takes no subcommand argument to run in the foreground (blocks the terminal, prints logs
inline — good for first-time setup and interactive login). Pass one of `start`, `stop`, or
`status` to manage it as a background daemon instead:

```bash
eahelper server                # foreground — first run / interactive login
eahelper server start          # background daemon; pidfile + logs under ~/.eahelper/
eahelper server status          # is it running, healthy, what port/pid
eahelper server stop            # stop the background daemon
```

```bash
eahelper server --url https://eu-10.leanix.net/MyWorkspace
eahelper server --api-token "your-api-key-here"
eahelper server --token "eyJhbGci..."
eahelper server --port 9000
eahelper server --cdp-port 19333
eahelper server --keep-browser
eahelper server --legacy-ssl
eahelper server --mcp-read-only
```

### Runtime endpoints (while `server` is running)

| Method | Path | Description |
|---|---|---|
| GET  | `/graphql` | GraphiQL interactive UI |
| POST | `/graphql` | GraphQL proxy to LeanIX |
| GET/POST | `/mcp` | Embedded MCP endpoint (streamable HTTP) — `get_schema` and `query` tools |
| GET  | `/health` | Health check + upstream URL |
| GET  | `/healthz` | Lightweight liveness probe — used by `eahelper server status` and health-check scripts |
| GET  | `/token` | Show masked current Bearer token |
| POST | `/token` | Replace the Bearer token at runtime |
| POST | `/token/refresh` | Force re-extraction from the managed browser |

```bash
curl http://localhost:8765/health
curl http://localhost:8765/healthz
curl -X POST http://localhost:8765/token -H "Content-Type: application/json" \
  -d '{"token": "eyJhbGci..."}'
curl -X POST http://localhost:8765/token/refresh
```

```powershell
Invoke-RestMethod http://localhost:8765/health
Invoke-RestMethod http://localhost:8765/healthz
Invoke-RestMethod -Uri http://localhost:8765/token -Method POST `
  -ContentType "application/json" -Body '{"token": "eyJhbGci..."}'
Invoke-RestMethod -Uri http://localhost:8765/token/refresh -Method POST
```

## `eahelper proxy` (legacy)

The standalone GraphQL proxy + GraphiQL UI from earlier versions. Still available,
but prefer `eahelper server`, which runs the same proxy plus the MCP endpoint and
managed browser in one process.

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
| `--proxy URL` | `http://localhost:8765/graphql` | GraphQL proxy URL — auto-starts `server` in the background if not reachable |
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
| `--db {kuzu,neo4j}` | `graph.db` in `config.toml`, else prompted | Target graph database |
| `--data-dir PATH` | `data/leanix` | Directory of previously downloaded JSON |
| `--mapping PATH` | see "The mapping file" below | Controls which types/relations are loaded and how they're named |
| `--generate-mapping` | off | Scan the live workspace and write `metamodel-mapping.yaml` to the CWD, then exit. Requires the proxy to be running |
| `--all-factsheets` | off | Import every FactSheet type from the live workspace, ignoring the mapping's `factsheet_types` filter (relationship mappings still apply) |
| `--limit N` | none | Cap rows loaded per type/relation — smoke test |
| `--skip-download` | n/a | (If load also triggers a download step) load only from existing JSON |

```bash
eahelper load --db kuzu
eahelper load --db neo4j
eahelper load --db kuzu --limit 10
eahelper load --db kuzu --mapping path/to/my-mapping.yaml
```

If `--db` is omitted and not set in `~/.eahelper/config.toml`, you'll be prompted interactively
and the answer is saved back. Default to `kuzu` unless the user has an existing Neo4j server or
explicitly wants Neo4j. `load` auto-starts `server` in the background if the proxy isn't already
reachable.

### The mapping file (`metamodel-mapping.yaml`)

The mapping YAML controls **which FactSheet types are downloaded/loaded** (`factsheet_types`
whitelist) and **how LeanIX relation fields become graph relationship types** (`relationships`
map, e.g. `relApplicationToBusinessCapability → SUPPORTS`). Both `download` and `load` use it.

Resolution order — the first match wins:

1. `--mapping PATH` — hard error if the file doesn't exist.
2. `./metamodel-mapping.yaml` in the current working directory.
3. The default mapping bundled inside the installed `dvm-eahelper` package.
4. Built-in hardcoded defaults.

The bundled default (step 3) covers a generic LeanIX metamodel; workspaces with custom FactSheet
types or relation fields will silently skip anything not listed. To make the mapping explicit and
workspace-specific, generate one from the live workspace and keep it in your project directory:

```bash
eahelper load --generate-mapping     # writes ./metamodel-mapping.yaml (proxy must be running)
```

Subsequent `download`/`load` runs from that directory pick it up automatically (step 2). Edit it
to rename relationship types or trim the `factsheet_types` list.

## `eahelper seed`

```bash
eahelper seed --db kuzu
eahelper seed --db neo4j
```

Clears the target database and loads a small built-in demo graph (~8 applications, 6 business
capabilities, 11 interfaces) — useful for verifying the DB setup or trying queries without any
LeanIX access.

## `eahelper config`

Manages `~/.eahelper/config.toml`. Precedence when eahelper resolves any setting: **CLI flag >
environment variable > `config.toml` > interactive prompt** (a prompt answer is saved back to
`config.toml`, so the user is asked at most once, ever).

| Command | Description |
|---|---|
| `eahelper config` | Print the effective, resolved config |
| `eahelper config set <section.key> <value>` | Set a value, e.g. `eahelper config set leanix.workspace_url https://eu-10.leanix.net/MyWorkspace` |
| `eahelper config unset <section.key>` | Remove a value, falling back to the next source in the precedence order |
| `eahelper config path` | Print the absolute path to `config.toml` |

Recognized sections/keys:

```toml
[leanix]
workspace_url = "https://eu-10.leanix.net/YourWorkspace"
proxy_port = 8765

[browser]
browser = "chrome"        # or "edge"
cdp_port = 19222
keep_open = false

[graph]
db = "kuzu"                # or "neo4j"
kuzu_path = "~/.eahelper/graph.kuzu"

[neo4j]
uri = "bolt://localhost:7687"
```

`NEO4J_PASSWORD` (and any other credential) is never written to `config.toml` — supply it via
environment variable or a `.env` file each time. See
[references/database-backends.md](references/database-backends.md).

```bash
eahelper config
eahelper config set leanix.workspace_url https://eu-10.leanix.net/MyWorkspace
eahelper config set graph.db kuzu
eahelper config unset browser.keep_open
eahelper config path
```

## `eahelper mcp`

Runs the MCP server over stdio instead of the HTTP endpoint embedded in `server`. Use this for
agents/clients that only support stdio transport, or when you don't want the full proxy/browser
supervisor running — just the graph query tools.

```bash
eahelper mcp
eahelper mcp --mcp-read-only
```

## `eahelper mcp-config`

Prints (or installs) MCP client config for Claude Code and VS Code/Copilot, offering both the
embedded HTTP endpoint (`http://localhost:8765/mcp`, requires `server` running) and the stdio
variant (`eahelper mcp`).

```bash
eahelper mcp-config              # print config to stdout for manual copy-paste
eahelper mcp-config --install    # write .mcp.json (Claude Code) and .vscode/mcp.json (Copilot) in the current project
```

## Typical end-to-end sequence

```bash
eahelper server start            # background daemon — first run prompts for workspace/db, opens+closes browser
eahelper download                # auto-starts server if needed
eahelper load --db kuzu          # auto-starts server if needed
eahelper mcp-config --install    # wire up MCP once per project
# then query via the agent's get_schema / query MCP tools
```

```powershell
# Windows — same commands, PowerShell-native equivalents only needed for
# browser-launch/health-check one-liners (see browser-setup.md, troubleshooting.md)
eahelper server start
eahelper download
eahelper load --db kuzu
eahelper mcp-config --install
```
