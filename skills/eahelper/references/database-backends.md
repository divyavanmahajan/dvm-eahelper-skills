# Database Backends: KuzuDB vs Neo4j

`eahelper load` and `eahelper seed` both take `--db {kuzu,neo4j}`. If omitted, you're prompted
interactively. **Default recommendation: KuzuDB**, unless the user already runs Neo4j or asks for
it specifically.

## KuzuDB (default)

- **Embedded, zero-install** — no server process, no Desktop app, no credentials. The graph is a
  directory/file on local disk (check `eahelper load --help` or the tool's config for the exact
  default path if you need to locate it).
- Fastest path to a working graph — good default for a single user exploring their workspace.
- Query it two ways:
  1. **Directly with the `kuzu` Python API**:
     ```python
     import kuzu
     db = kuzu.Database("path/to/kuzu-db")
     conn = kuzu.Connection(db)
     result = conn.execute("MATCH (a:Application) RETURN a.name LIMIT 10")
     while result.has_next():
         print(result.get_next())
     ```
  2. **Via an MCP server**, so Claude Code / Copilot can query in natural language. Example
     `.mcp.json` entry (Claude Code) using a Kuzu MCP server run through `uvx`:
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
     Adjust the package name/flags to whatever Kuzu MCP server the user has installed — check
     `uvx mcp-server-kuzu --help` (or the equivalent package) before assuming exact flag names, as
     MCP server packages for Kuzu are less standardized than the Neo4j one.

## Neo4j (optional)

Requires:
1. **A running Neo4j server** — start the DBMS in Neo4j Desktop (or any Neo4j 5.x instance)
   *before* running `eahelper load --db neo4j`.
2. **A `.env` file** in the working directory:
   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password_here
   ```
   Never commit `.env` — see the repo's `.gitignore`.
3. Optionally, the **APOC plugin** installed in Neo4j Desktop (DBMS → Plugins tab) for full schema
   introspection via `get_neo4j_schema` in the MCP server below.

### Verifying a Neo4j load

Open Neo4j Browser at `http://localhost:7474` and run:

```cypher
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC;
MATCH (a:Application) RETURN a.name LIMIT 10;
MATCH ()-[r]->() RETURN type(r), count(r) ORDER BY count(r) DESC LIMIT 20;
```

### Querying via MCP — `mcp-neo4j-cypher`

Exposes three tools: `read_neo4j_cypher`, `write_neo4j_cypher`, `get_neo4j_schema` (requires
APOC).

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
them.

## Choosing between them

| Situation | Use |
|---|---|
| First time trying the tool, no infra to stand up | `kuzu` |
| Single user, ad-hoc exploration | `kuzu` |
| Team already has a shared Neo4j server | `neo4j` |
| Need Neo4j Browser's visual graph exploration | `neo4j` |
| Want zero external services / fully local | `kuzu` |
