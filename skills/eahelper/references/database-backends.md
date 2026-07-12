# Database Backends: KuzuDB vs Neo4j

`eahelper load` and `eahelper seed` both take `--db {kuzu,neo4j}`. If omitted, you're prompted
interactively (and the answer is saved to `~/.eahelper/config.toml` under `graph.db`). **Default
recommendation: KuzuDB**, unless the user already runs Neo4j or asks for it specifically.

Both backends are queried the same way in the primary workflow: the **embedded MCP endpoint**
served by `eahelper server` (streamable HTTP at `http://localhost:8765/mcp`, or stdio via
`eahelper mcp`). It exposes the same two tools — `get_schema` and `query` — regardless of which
database is behind it. Run `eahelper mcp-config --install` once per project to wire this up for
Claude Code / VS Code, then use the tools directly rather than shelling out to `kuzu`/`cypher-shell`.

## KuzuDB (default)

- **Embedded, zero-install** — no server process, no Desktop app, no credentials. The graph is a
  directory/file on local disk (default path is set under `graph.kuzu_path` in
  `~/.eahelper/config.toml`; check `eahelper config` or `eahelper load --help` for the exact
  current default).
- Fastest path to a working graph — good default for a single user exploring their workspace.
- **Single-writer lock**: only one process can hold KuzuDB open for writes at a time. If
  `eahelper server`'s embedded MCP endpoint has the database open and you run `eahelper load`
  concurrently (or vice versa), one of them will fail or block on the lock — see
  [troubleshooting.md](troubleshooting.md).
- Query it three ways, in order of recommendation:
  1. **Embedded MCP endpoint** (recommended) — `eahelper mcp-config --install`, then use
     `get_schema` / `query` from your agent. No extra process, no separate package to install.
  2. **External Kuzu MCP server** (fallback) — if you have a standalone `kuzu-mcp-server` (or
     similar) already configured, it still works, but note this class of external Kuzu MCP server
     packages is generally **archived/unmaintained** upstream — prefer the embedded endpoint above
     for anything new. Example `.mcp.json` entry (Claude Code) using such a server via `uvx`:
     ```json
     {
       "mcpServers": {
         "kuzu": {
           "command": "uvx",
           "args": ["mcp-server-kuzu", "--db-path", "/absolute/path/to/kuzu-db"]
         }
       }
     }
     ```
     Verify the package still installs and check `--help` before relying on it — flag names and
     maintenance status vary and may have drifted.
  3. **Directly with the `kuzu` Python API** (ad hoc / scripting only — do not run this while
     `eahelper server`'s MCP endpoint has the DB open, per the single-writer note above):
     ```python
     import kuzu
     db = kuzu.Database("path/to/kuzu-db")
     conn = kuzu.Connection(db)
     result = conn.execute("MATCH (a:Application) RETURN a.name LIMIT 10")
     while result.has_next():
         print(result.get_next())
     ```

## Neo4j (optional)

Requires:
1. **A running Neo4j server** — start the DBMS in Neo4j Desktop (or any Neo4j 5.x instance)
   *before* running `eahelper load --db neo4j` or `eahelper server` with `graph.db = "neo4j"`.
2. **Connection settings**. The URI/username can be stored in `~/.eahelper/config.toml` under
   `[neo4j] uri = "bolt://localhost:7687"`, but the **password is never persisted there** — set
   `NEO4J_PASSWORD` via environment variable or a `.env` file each time:
   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password_here
   ```
   Never commit `.env` — see the repo's `.gitignore`.
3. Optionally, the **APOC plugin** installed in Neo4j Desktop (DBMS → Plugins tab) for full schema
   introspection.

### Verifying a Neo4j load

Open Neo4j Browser at `http://localhost:7474` and run:

```cypher
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC;
MATCH (a:Application) RETURN a.name LIMIT 10;
MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY count(r) DESC LIMIT 20;
```

### Querying via MCP

**Recommended: the embedded endpoint.** `eahelper server` with `graph.db = "neo4j"` serves the
same `get_schema` / `query` MCP tools at `http://localhost:8765/mcp` as it does for KuzuDB. Run
`eahelper mcp-config --install` once per project and use the tools from your agent — no separate
Neo4j MCP package required.

**Fallback: `mcp-neo4j-cypher`.** If you have this external server already configured, it remains
a documented, supported fallback. It exposes three tools: `read_neo4j_cypher`,
`write_neo4j_cypher`, `get_neo4j_schema` (requires APOC).

**Claude Code** (`.mcp.json`, project or user-level):

```json
{
  "mcpServers": {
    "neo4j": {
      "command": "uvx",
      "args": [
        "mcp-neo4j-cypher",
        "--db-url", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "your_password_here"
      ]
    }
  }
}
```

**GitHub Copilot in VS Code** (`.vscode/settings.json`):

```json
{
  "github.copilot.chat.mcp.servers": {
    "neo4j": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "mcp-neo4j-cypher",
        "--db-url", "bolt://localhost:7687",
        "--username", "neo4j",
        "--password", "your_password_here"
      ]
    }
  }
}
```

Do not commit real passwords in either file — prefer a user-level settings override, or reference
an environment variable if the MCP server supports it.

### Example Cypher patterns

```cypher
// Apps supporting a capability
MATCH (a:Application)-[:SUPPORTS]->(b:BusinessCapability {name: "Order Management"})
RETURN a.name

// Interfaces out of an app and the data they carry
MATCH (src:Application {name: "CRM System"})-[:EXPOSES]->(i:Interface)-[:CONSUMED_BY]->(tgt:Application)
RETURN i.name, i.protocol, [(i)-[:CARRIES]->(d) | d.name] AS dataObjects

// Full map: app -> capabilities + who it sends data to
MATCH (a:Application)
OPTIONAL MATCH (a)-[:SUPPORTS]->(b:BusinessCapability)
OPTIONAL MATCH (a)-[:EXPOSES]->(i:Interface)-[:CONSUMED_BY]->(tgt:Application)
RETURN a.name, collect(DISTINCT b.name) AS capabilities, collect(DISTINCT tgt.name) AS sends_to
```

Use these same patterns as the `query` argument for the embedded MCP `query` tool — they work
unchanged against either backend.

## Graph model (both backends)

```
(Application)-[:SUPPORTS]->(BusinessCapability)
(Application)-[:EXPOSES]->(Interface)-[:CONSUMED_BY]->(Application)
(Interface)-[:CARRIES]->(DataObject)
(Application)-[:OWNED_BY]->(Organization)
(BusinessCapability)-[:CHILD_OF]->(BusinessCapability)
```

Node labels: `PascalCase`. Relationship types: `UPPER_SNAKE_CASE`. Property names: `camelCase`.
The LeanIX `id` (UUID) is the stable identifier used for idempotent `MERGE`-based loads in both
backends — re-running `eahelper load` updates existing nodes/relationships rather than duplicating
them. Call the MCP `get_schema` tool to confirm the exact labels/properties present in a given
graph rather than assuming this model is complete for every workspace.

## Choosing between them

| Situation | Use |
|---|---|
| First time trying the tool, no infra to stand up | `kuzu` |
| Single user, ad-hoc exploration | `kuzu` |
| Team already has a shared Neo4j server | `neo4j` |
| Need Neo4j Browser's visual graph exploration | `neo4j` |
| Want zero external services / fully local | `kuzu` |

Regardless of choice, the embedded MCP endpoint (`eahelper mcp-config --install`) is the
recommended way to query — it's the same setup either way, so switching backends later doesn't
change how the agent queries the graph.
