# Troubleshooting

## Browser / CDP connection

**`Could not connect to browser at http://localhost:9222`**
Cause: Edge/Chrome was already running, so the new window silently ignored
`--remote-debugging-port`.
Fix: close all windows of that browser, or (better) launch a separate isolated instance with a
distinct `--user-data-dir` — see [browser-setup.md](browser-setup.md). Verify before retrying:

```bash
curl -s http://localhost:9222/json/version        # macOS
```
```powershell
Invoke-RestMethod http://localhost:9222/json/version   # Windows
```
Both must return JSON. A connection error means the debug port never opened.

**`Timed out waiting for a Bearer token`**
Cause: no LeanIX API call was observed on the debugged browser.
Fix: make sure you actually logged in, then navigate within LeanIX (e.g. open the Inventory) to
trigger a real API request — the proxy needs to see one go by to capture the Authorization header.

**Saved token immediately invalid / wrong workspace**
Cause: a token cached from a previous run was for a different LeanIX workspace.
Fix: force fresh extraction by re-running with `--connect` explicit, or delete the cached token
file and restart `eahelper proxy`.

## Proxy / download / load ordering

**`Connection refused` when running `eahelper download` or `eahelper load`**
Cause: `eahelper proxy` is not running, or is running on a different port than `--proxy` expects.
Fix: start `eahelper proxy` first, in its own terminal, and leave it running for the duration of
the download. Confirm it's up:

```bash
curl http://localhost:8765/health
```
```powershell
Invoke-RestMethod http://localhost:8765/health
```

**Queries return `TOKEN_EXPIRED`**
Cause: the LeanIX browser session expired mid-run.
Fix: `POST /token/refresh` to re-extract from the still-open debug browser, or restart
`eahelper proxy`.

```bash
curl -X POST http://localhost:8765/token/refresh
```
```powershell
Invoke-RestMethod -Uri http://localhost:8765/token/refresh -Method POST
```

**Port already in use**
Cause: something else is bound to 8765 (or 9222).
Fix: `eahelper proxy --port 9000` and pass `--proxy http://localhost:9000/graphql` to `download`.

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
   eahelper proxy --ca-bundle "$env:USERPROFILE\.eahelper\corporate-ca.pem"
   ```
   On macOS, export the system/corporate root CA from Keychain Access to a `.pem` file and pass it
   the same way via `--ca-bundle`.

3. **Relax strict X.509 validation** (fixes MITM certs missing `Authority Key Identifier`):
   ```bash
   eahelper proxy --legacy-ssl
   eahelper download --legacy-ssl
   ```

4. **Disable verification entirely** (quick local test only, not recommended):
   ```bash
   eahelper proxy --no-verify-ssl
   ```

## Neo4j-specific

**`Connection refused` (Neo4j)**
Cause: the database isn't started.
Fix: start the DBMS in Neo4j Desktop before running `eahelper load --db neo4j`.

**`Authentication failed` / `AuthError`**
Cause: `.env` credentials don't match the Neo4j Desktop password.
Fix: check `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` in `.env` against the DBMS settings.

**`get_neo4j_schema` MCP tool fails or returns nothing**
Cause: the APOC plugin isn't installed.
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

## General diagnostics checklist

When something fails and the cause isn't obvious, check in this order:
1. Is the debug browser still open, on port 9222, and still logged in to LeanIX?
2. Is `eahelper proxy` still running in its own terminal? (`curl http://localhost:8765/health`)
3. Is the workspace URL correct for this LeanIX tenant?
4. Corporate network? Run `eahelper diagnose`.
5. For `--db neo4j`: is the Neo4j DBMS started, and does `.env` match its credentials?
