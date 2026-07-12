---
name: eahelper
description: Work with SAP LeanIX using the dvm-eahelper CLI - install it, run the GraphQL proxy against an already-logged-in browser, download factsheets, load them into KuzuDB (default) or Neo4j, and query the resulting graph.
---

# eahelper — SAP LeanIX Graph Workflow

`eahelper` is a unified CLI (PyPI package `dvm-eahelper`) with five subcommands:

| Subcommand | Purpose |
|---|---|
| `proxy`    | Start a local GraphQL proxy that forwards to LeanIX, authenticated via an already-logged-in browser (or a Technical User API key) |
| `diagnose` | Test SSL/TLS connectivity and recommend a fix for corporate proxy issues |
| `download` | Fetch factsheets and relationships from LeanIX via the proxy, save as JSON |
| `load`     | Load downloaded JSON into a graph database — KuzuDB (default, embedded) or Neo4j (`--db kuzu\|neo4j`) |
| `seed`     | Load a small self-contained demo graph, no LeanIX access needed |

Follow the workflow below in order. Do not skip the browser-launch step — it is the most common
source of failures. Full detail for each step lives in `references/`; only pull those files in
when you need more than the summary here.

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

## 1. Launch a debug browser and log in to LeanIX

The proxy authenticates by attaching to an **already-running, already-logged-in** browser over
Chrome DevTools Protocol (CDP) on port 9222. A normal browser window will NOT work — you must
launch a separate, isolated instance with its own profile directory, because an already-running
Chrome/Edge silently ignores `--remote-debugging-port` on a new window.

```powershell
# Windows — Edge (recommended, preinstalled)
Start-Process "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  "--remote-debugging-port=9222 --user-data-dir=C:\Temp\edge-debug --no-first-run --no-default-browser-check"

# Verify the debug port is open
Invoke-RestMethod http://localhost:9222/json/version
```

```bash
# macOS — Chrome
open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-debug"

# Verify the debug port is open
curl -s http://localhost:9222/json/version
```

Both commands must return JSON containing the browser version. If they don't, see
[references/troubleshooting.md](references/troubleshooting.md).

In the window that opens, **log in to your LeanIX workspace** before continuing. Leave it open.

Full platform detail, alternate browsers, and profile-path notes:
[references/browser-setup.md](references/browser-setup.md).

## 2. Start the proxy

In a separate terminal, with the debug browser still open and logged in:

```bash
eahelper proxy
# or, explicitly:
eahelper proxy --url https://eu-10.leanix.net/YourWorkspace
```

You'll be prompted for the workspace URL if not supplied. The proxy extracts a Bearer token from
the browser via CDP and serves:
- GraphiQL UI at `http://localhost:8765/graphql`
- Health check at `http://localhost:8765/health`

Leave this terminal running — `download` and `load` need the proxy alive.

If you hit SSL errors (common on corporate networks), run `eahelper diagnose` first and apply its
recommended fix (usually a `--legacy-ssl` or `--ca-bundle` flag). See
[references/troubleshooting.md](references/troubleshooting.md).

## 3. Download factsheets

In a new terminal (proxy still running in the other one):

```bash
# See what's available first
eahelper download --list-types

# Download everything the tool knows how to map, or specific types
eahelper download
eahelper download --type Application --output data/leanix/Application.json
```

Full flag reference: [references/cli-reference.md](references/cli-reference.md).

## 4. Load into a graph database

```bash
eahelper load --db kuzu     # default, embedded, zero-install — recommended to start
eahelper load --db neo4j    # requires a running Neo4j server + .env credentials
```

If `--db` is omitted, `eahelper` prompts interactively; **default to `kuzu`** unless the user has
an existing Neo4j deployment or explicitly asks for Neo4j.

For Neo4j, a `.env` file must exist with:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password_here
```

See [references/database-backends.md](references/database-backends.md) for the KuzuDB vs Neo4j
tradeoffs, storage locations, and idempotency notes.

## 5. (Optional) Seed a demo graph instead

No LeanIX access needed — useful for trying queries or verifying the DB setup:

```bash
eahelper seed --db kuzu
```

## 6. Query the graph

- **KuzuDB** (default): query directly with the `kuzu` Python API, or connect an MCP server (e.g.
  `mcp-server-kuzu`) so Claude Code / Copilot can query in natural language.
- **Neo4j**: use the `mcp-neo4j-cypher` MCP server (stdio, launched via `uvx`) for natural-language
  Cypher queries in Claude Code or GitHub Copilot Chat.

Full MCP server configs (JSON for both `.mcp.json` / Claude Code and VS Code `settings.json` /
Copilot) and example Cypher/Kuzu queries: [references/database-backends.md](references/database-backends.md).

## Troubleshooting

Common failure points — port 9222 not open, "timed out waiting for a Bearer token", running
`load`/`download` before `proxy` is up, SSL/corporate-proxy certificate errors, Neo4j auth
failures, stale/expired tokens — are all covered with exact fixes in
[references/troubleshooting.md](references/troubleshooting.md). Check there before improvising a
fix.
