# Troubleshooting

## Server logs and pidfile locations

Before digging into specific symptoms, know where to look:
- **Background daemon logs**: `~/.eahelper/server.log` (stdout/stderr of `eahelper server start`).
  Tail it when `eahelper server status` reports something is wrong but doesn't say why.
- **Pidfile**: `~/.eahelper/server.pid` — used by `eahelper server status`/`stop` to find the
  running daemon.
- **Config**: `~/.eahelper/config.toml` — `eahelper config path` prints the exact path.
- **Managed browser profile**: `~/.eahelper/browser-profile`.

```bash
tail -f ~/.eahelper/server.log        # macOS/Linux
eahelper server status
```

```powershell
Get-Content "$env:USERPROFILE\.eahelper\server.log" -Wait -Tail 50
eahelper server status
```

## Browser / CDP connection

**`Could not connect to browser at http://localhost:19222`**
Cause: something already bound to port 19222 that isn't the managed browser, or the managed
browser failed to launch (e.g. Playwright Chromium runtime missing, or process spawn blocked by
policy).
Fix:
1. Check what's on the port:
   ```bash
   curl -s http://localhost:19222/json/version        # macOS
   ```
   ```powershell
   Invoke-RestMethod http://localhost:19222/json/version   # Windows
   ```
   If it returns JSON but looks unrelated to your session, something else owns 19222 — stop it, or
   run `eahelper server --cdp-port 19333` (also update `eahelper config set browser.cdp_port
   19333`) to use a different port.
2. If nothing responds at all, confirm Playwright's Chromium runtime is installed (see
   [install.md](install.md)) and re-run `eahelper server`.
3. If the managed browser still won't launch, fall back to a manually-launched debug browser — see
   [browser-setup.md](browser-setup.md) — and pass `--cdp-port` to match wherever you launched it.

**Port 19222 conflict with another tool**
Some other CDP-based tool (another browser automation script, a different agent, a leftover
manually-launched browser from an older workflow) may already hold port 19222. Since `eahelper`
switched from the old `9222` convention specifically to reduce collisions with default CDP
tooling, check for stragglers still using `9222` too if you're migrating from an older setup — they
won't conflict with `19222`, but a leftover process from a previous manual launch on `19222` will.
Kill the stray process or use `--cdp-port` to pick a free one.

**Edge on Windows: browser won't attach / port never opens**
Cause: Edge's CDP support requires **every** Edge window and background process to be fully closed
before a new debug instance can bind the port — a single leftover window (including one kept alive
by "continue running background apps" settings) is enough to silently break it.
Fix: close all Edge windows (check Task Manager for `msedge.exe` processes lingering after you
think you've closed them), then retry. `eahelper` detects this case and will warn you and prompt
before proceeding when Edge is the target browser. If this keeps happening, switch to Chrome as
the managed browser: `eahelper server --browser chrome` (or `eahelper config set browser.browser
chrome`) — Chrome does not have this restriction.

**`Timed out waiting for a Bearer token`**
Cause: no LeanIX API call was observed on the debugged browser (managed or manual).
Fix: make sure you actually logged in, then navigate within LeanIX (e.g. open the Inventory) to
trigger a real API request — `eahelper` needs to see one go by to capture the Authorization header.

**Saved token immediately invalid / wrong workspace**
Cause: a token cached from a previous run was for a different LeanIX workspace.
Fix: force fresh extraction with `curl -X POST http://localhost:8765/token/refresh` while the
server is running, or delete `~/.eahelper/browser-profile` to force a completely clean login, then
restart `eahelper server`.

## Server / download / load ordering

**`Connection refused` when running `eahelper download` or `eahelper load`**
Cause: normally self-healing — both commands auto-start `eahelper server` in the background if the
proxy isn't reachable. If you still see this, the auto-start itself likely failed (check
`~/.eahelper/server.log`), or `--proxy`/`--port` point at a different port than the server is
actually using.
Fix: start the server explicitly and watch the output:
```bash
eahelper server start
eahelper server status
curl http://localhost:8765/health
```
```powershell
eahelper server start
eahelper server status
Invoke-RestMethod http://localhost:8765/health
```

**`eahelper server status` says stopped, but you're sure you started it (stale pidfile)**
Cause: the process behind `~/.eahelper/server.pid` died (crash, machine sleep/wake, forced kill)
without cleaning up its own pidfile, so `status`/`start` get confused about whether it's really
running.
Fix:
```bash
eahelper server stop     # should no-op cleanly, but clears a genuinely stale pidfile
eahelper server start
```
If `stop` also hangs or errors, manually remove the stale pidfile and retry:
```bash
rm ~/.eahelper/server.pid && eahelper server start
```
```powershell
Remove-Item "$env:USERPROFILE\.eahelper\server.pid" -ErrorAction SilentlyContinue
eahelper server start
```
Then confirm with `eahelper server status` and check `~/.eahelper/server.log` for why the previous
instance died.

**Queries return `TOKEN_EXPIRED`**
Cause: the LeanIX browser session expired mid-run.
Fix: `POST /token/refresh` to force re-extraction (the managed browser will reopen briefly to
recapture, then close itself again), or restart `eahelper server`.

```bash
curl -X POST http://localhost:8765/token/refresh
```
```powershell
Invoke-RestMethod -Uri http://localhost:8765/token/refresh -Method POST
```

**Port already in use**
Cause: something else is bound to 8765 (proxy/MCP port) or 19222 (CDP port).
Fix: `eahelper server --port 9000 --cdp-port 19333`, then pass `--proxy http://localhost:9000/graphql`
to `download`/`load`, and update `.mcp.json`/`.vscode/mcp.json` (re-run `eahelper mcp-config
--install` after changing the port) to point at the new port.

## KuzuDB single-writer lock conflicts

**`load` fails with a lock/"database is being used by another process" error while `server` is running**
Cause: KuzuDB only allows one process to hold the database open for writes at a time. If
`eahelper server`'s embedded MCP endpoint has the KuzuDB file open (e.g. an agent is mid-query, or
the server just has it open idly) and you run `eahelper load --db kuzu` concurrently, one of the
two will fail to acquire the lock.
Fix: stop the server (or at minimum ensure no MCP query is in flight) before running a KuzuDB
`load`, then restart the server afterward:
```bash
eahelper server stop
eahelper load --db kuzu
eahelper server start
```
If `load` auto-started the server itself and then also needs the write lock, prefer running `load`
first, before starting the server for interactive querying, to avoid the race entirely. This
constraint is specific to KuzuDB; Neo4j's server process handles concurrent readers/writers itself
and does not have this restriction.

## SSL / corporate proxy

**`SSL: CERTIFICATE_VERIFY_FAILED` — self-signed certificate in chain**
Cause: a corporate SSL-inspection proxy (e.g. Zscaler, Netskope, Palo Alto Prisma) replaces
certificates with ones signed by an internal CA that Python doesn't trust, and/or the MITM
certificate is missing the `Authority Key Identifier` extension that Python 3.13+ requires.

Fix, in order of preference:

1. **Diagnose first:**
   ```bash
   eahelper diagnose
   ```
   This runs DNS → TCP → TLS → HTTP checks and prints the exact recommended fix.

2. **Point at the corporate CA bundle** (best option — keeps verification on):
   ```powershell
   $certs = Get-ChildItem -Path Cert:\LocalMachine\Root
   $pem = $certs | ForEach-Object { "-----BEGIN CERTIFICATE-----`n" + [Convert]::ToBase64String($_.RawData, 'InsertLineBreaks') + "`n-----END CERTIFICATE-----" }
   $pem | Set-Content -Path "$env:USERPROFILE\.eahelper\corporate-ca.pem" -Encoding ascii
   eahelper server --ca-bundle "$env:USERPROFILE\.eahelper\corporate-ca.pem"
   ```
   On macOS, export the system/corporate root CA from Keychain Access to a `.pem` file and pass it
   the same way via `--ca-bundle`.

3. **Relax strict X.509 validation** (fixes MITM certs missing `Authority Key Identifier`):
   ```bash
   eahelper server --legacy-ssl
   eahelper download --legacy-ssl
   ```

4. **Disable verification entirely** (quick local test only, not recommended):
   ```bash
   eahelper server --no-verify-ssl
   ```

## Neo4j-specific

**`Connection refused` (Neo4j)**
Cause: the database isn't started.
Fix: start the DBMS in Neo4j Desktop before running `eahelper load --db neo4j` or `eahelper
server` with `graph.db = "neo4j"`.

**`Authentication failed` / `AuthError`**
Cause: credentials don't match the Neo4j Desktop password — either `.env`/environment
`NEO4J_PASSWORD`, or a stale `[neo4j] uri`/username in `config.toml`.
Fix: check `NEO4J_URI`/`NEO4J_USERNAME` (`eahelper config`) and `NEO4J_PASSWORD` (env/.env) against
the DBMS settings.

**`get_neo4j_schema` MCP tool fails or returns nothing (external `mcp-neo4j-cypher` fallback only)**
Cause: the APOC plugin isn't installed. Not applicable when using the embedded MCP `get_schema`
tool, which doesn't require APOC.
Fix: Neo4j Desktop → your DBMS → Plugins tab → install APOC → restart the DBMS.

## Data / mapping

**Empty download for a type**
Cause: the FactSheet type doesn't exist in this workspace, or isn't in the mapping whitelist.
Fix: `eahelper download --list-types` to see what's actually available; use `--all-factsheets` to
bypass any mapping filter.

**Permission-denied errors for specific fields**
LeanIX returns partial data alongside GraphQL errors for fields your user can't read (e.g.
`No permission: fact_sheet_fields:read:application:lx__financial_critical_application`). The
downloader detects this automatically, excludes the field, and retries — a warning lists what was
excluded. This is expected behavior, not a bug to fix.

**Unmapped relationship type shows up oddly named in the graph**
Cause: a LeanIX relation field isn't in `metamodel-mapping.yaml`'s explicit relationship mapping.
Fix: it falls back to an auto camelCase → UPPER_SNAKE_CASE conversion. Add an explicit entry to
the mapping YAML if you want a different name.

## MCP-specific

**Agent can't see `get_schema`/`query` tools after `eahelper mcp-config --install`**
Cause: most agents only read MCP config at startup.
Fix: fully restart/reload the agent (Claude Code: restart the session; VS Code: reload window)
after running `--install`. Confirm the config was written where expected (`.mcp.json` for Claude
Code, `.vscode/mcp.json` for Copilot) and that `eahelper server` is actually running if you're
using the HTTP variant.

**`query` tool errors with a permissions/read-only message**
Cause: the server was started with `--mcp-read-only`, which restricts the `query` tool to
read-only Cypher.
Fix: this is intentional if the user asked for it. To allow writes, restart the server without that
flag: `eahelper server stop && eahelper server start`.

## General diagnostics checklist

When something fails and the cause isn't obvious, check in this order:
1. Is `eahelper server` running and healthy? `eahelper server status` or `curl
   http://localhost:8765/healthz`.
2. Check `~/.eahelper/server.log` for the actual error.
3. If browser/token related: was the managed browser able to open, log in, and capture a token? On
   Windows with Edge, are all Edge windows fully closed?
4. Is the workspace URL correct for this LeanIX tenant? `eahelper config`.
5. Corporate network? Run `eahelper diagnose`.
6. For `--db neo4j`: is the Neo4j DBMS started, and do `config.toml`/`.env` match its credentials?
7. For `--db kuzu`: is another `eahelper` process (server or a concurrent `load`) already holding
   the write lock?
