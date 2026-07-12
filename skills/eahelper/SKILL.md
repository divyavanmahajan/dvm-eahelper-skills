---
name: eahelper
description: Work with SAP LeanIX using the dvm-eahelper CLI - install it, run the integrated server (GraphQL proxy + embedded MCP endpoint + managed debug browser), download factsheets, load them into KuzuDB (default) or Neo4j, and query the resulting graph over MCP.
---

# eahelper — SAP LeanIX Graph Workflow

`eahelper` is a unified CLI (PyPI package `dvm-eahelper`). As of v0.2.0 it centers on one
supervisor process, `eahelper server`, that bundles the GraphQL proxy, an embedded MCP endpoint,
and a managed debug browser — no more juggling a manually-launched browser and a separate proxy
terminal.

| Subcommand | Purpose |
|---|---|
| `server`      | Run the supervisor: GraphQL proxy (port 8765) + embedded MCP endpoint (`/mcp`) + managed debug browser. Foreground by default; `start\|stop\|status` manage it as a background daemon. |
| `diagnose`    | Test SSL/TLS connectivity and recommend a fix for corporate proxy issues |
| `download`    | Fetch factsheets and relationships from LeanIX via the proxy, save as JSON |
| `load`        | Load downloaded JSON into a graph database — KuzuDB (default, embedded) or Neo4j (`--db kuzu\|neo4j`) |
| `seed`        | Load a small self-contained demo graph, no LeanIX access needed |
| `config`      | Show/set/unset persisted settings in `~/.eahelper/config.toml` |
| `mcp`         | Run the MCP server over stdio (for agents that only support stdio transport) |
| `mcp-config`  | Print or install MCP client config for Claude Code / VS Code (Copilot) |

Follow the workflow below in order. Full detail for each step lives in `references/`; only pull
those files in when you need more than the summary here.

## 0. Prerequisite check & install

Confirm Python 3.11+ and `uv` are available, then install the tool:

```bash
# macOS / Linux
python3 --version                       # must be 3.11+
curl -LsSf https://astral.sh/uv/install.sh | sh   # if uv is missing
uv tool install dvm-eahelper
uv tool run --from dvm-eahelper playwright install chromium   # one-time browser binaries
```

```powershell
# Windows (PowerShell)
python --version                         # must be 3.11+
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # if uv is missing
uv tool install dvm-eahelper
uv tool run --from dvm-eahelper playwright install chromium
```

`eahelper` can also be run without installing: `uvx dvm-eahelper -- <subcommand> ...`.

Optionally run the bundled prereq checker (`scripts/check_prereqs.py`) — see
[references/install.md](references/install.md) for full install/troubleshooting detail and what
the script checks.

```bash
python scripts/check_prereqs.py
```

## 1. Start the server

```bash
eahelper server
```

On first run, if `~/.eahelper/config.toml` doesn't have a workspace URL or database choice yet,
`eahelper server` prompts for them interactively and saves the answers back to that file — you
are asked at most once. It then opens a managed, isolated debug browser window automatically (CDP
port 19222, persistent profile at `~/.eahelper/browser-profile`) so you can log in to LeanIX. Once
a token is captured, the browser **closes itself automatically** — you don't need to manage or
leave a browser window open.

Log in to your LeanIX workspace in the window that opens, then wait for it to close on its own and
for the server to report it's ready. Because the browser profile is persistent, SSO cookies
usually survive between runs — after the first login you typically won't be prompted again.

`eahelper server` runs in the **foreground** by default and blocks the terminal. To run it as a
background daemon instead (recommended once you're past first-time setup):

```bash
eahelper server start     # launches in the background, writes a pidfile + logs under ~/.eahelper/
eahelper server status    # check whether it's up and healthy
eahelper server stop      # stop the background daemon
```

Full platform detail (managed vs. manual browser, Windows Edge-vs-Chrome guidance, persistent
profile) and the daemon file locations: [references/browser-setup.md](references/browser-setup.md)
and [references/cli-reference.md](references/cli-reference.md).

If you hit SSL errors (common on corporate networks), run `eahelper diagnose` first and apply its
recommended fix (usually a `--legacy-ssl` or `--ca-bundle` flag). See
[references/troubleshooting.md](references/troubleshooting.md).

## 2. Download factsheets

```bash
# See what's available first
eahelper download --list-types

# Download everything the tool knows how to map, or specific types
eahelper download
eahelper download --type Application --output data/leanix/Application.json
```

`download` auto-starts the server in the background if the proxy isn't already reachable, so a
second terminal is no longer required — but starting `server` yourself first is still the
recommended path for first-time LeanIX login.

Full flag reference: [references/cli-reference.md](references/cli-reference.md).

## 3. Load into a graph database

```bash
eahelper load --db kuzu     # default, embedded, zero-install — recommended to start
eahelper load --db neo4j    # requires a running Neo4j server + credentials
```

Like `download`, `load` auto-starts the server in the background if needed. If `--db` is omitted
and no default is set in `~/.eahelper/config.toml`, `eahelper` prompts interactively; **default to
`kuzu`** unless the user has an existing Neo4j deployment or explicitly asks for Neo4j.

For Neo4j, the connection URI/username can live in `~/.eahelper/config.toml`, but the password is
never stored there — set `NEO4J_PASSWORD` via environment variable or a `.env` file.

**Mapping:** which types get loaded and how relations are named is controlled by
`metamodel-mapping.yaml`, resolved as: `--mapping PATH` → `./metamodel-mapping.yaml` in the CWD →
the default bundled in the package → built-in defaults. If nothing local exists, the **bundled
default is used silently** — for workspaces with custom FactSheet types, generate an explicit
workspace-specific mapping first with `eahelper load --generate-mapping` (writes
`./metamodel-mapping.yaml`, picked up automatically afterwards). Full detail:
[references/cli-reference.md](references/cli-reference.md).

See [references/database-backends.md](references/database-backends.md) for the KuzuDB vs Neo4j
tradeoffs, storage locations, and idempotency notes.

## 4. (Optional) Seed a demo graph instead

No LeanIX access needed — useful for trying queries or verifying the DB setup:

```bash
eahelper seed --db kuzu
```

## 5. Query the graph over MCP

The server exposes an embedded MCP endpoint (streamable HTTP at `http://localhost:8765/mcp`) that
works identically for both KuzuDB and Neo4j — no separate third-party MCP server process needed
for the primary workflow. Wire it up, then query:

```bash
eahelper mcp-config --install
```

This installs the MCP client config for whichever agent you're running in (Claude Code's
`.mcp.json`, and/or VS Code/Copilot's `.vscode/mcp.json`), offering both the HTTP endpoint and a
stdio variant (`eahelper mcp`). Run it once per project, then reload/restart your agent so it picks
up the new MCP server.

Once connected, use the MCP tools directly instead of writing Cypher by hand outside the agent:
- `get_schema` — discover node labels, relationship types, and properties in the loaded graph.
- `query` — run a Cypher query against the graph. Read-write by default; pass `--mcp-read-only` at
  server-start time to restrict the server to read-only queries.

Example flow: call `get_schema` first, then `query` with `MATCH (a:Application) RETURN a.name
LIMIT 10` (adjust labels/properties to what `get_schema` reports).

If you need external/legacy MCP servers instead (e.g. an already-configured `kuzu-mcp-server` or
`mcp-neo4j-cypher`), see [references/database-backends.md](references/database-backends.md) for
those as documented fallbacks.

## Troubleshooting

Common failure points — port 19222 conflicts, Edge-on-Windows requiring all windows closed first,
KuzuDB's single-writer lock conflicting between the server's MCP endpoint and a concurrent `load`,
stale pidfiles, "timed out waiting for a Bearer token", SSL/corporate-proxy certificate errors, and
Neo4j auth failures — are all covered with exact fixes in
[references/troubleshooting.md](references/troubleshooting.md). Check there before improvising a
fix.
