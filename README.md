# dvm-eahelper-skills

An [Agent Skill](https://agentskills.io) that teaches AI coding agents (Claude Code, GitHub
Copilot) how to work with the [`dvm-eahelper`](https://pypi.org/project/dvm-eahelper/) Python
package for SAP LeanIX — installing it, running its integrated server (GraphQL proxy + embedded
MCP endpoint + managed debug browser), downloading factsheets, loading them into a graph database
(KuzuDB by default, or Neo4j), and querying the result over MCP.

This repo contains a single skill, `eahelper`, following the open Agent Skills standard: a folder
with a `SKILL.md` (YAML frontmatter + markdown instructions), plus `references/` for detail the
agent pulls in on demand and `scripts/` for a cross-platform prerequisite checker.

```
skills/eahelper/
├── SKILL.md
├── references/
│   ├── install.md
│   ├── browser-setup.md
│   ├── cli-reference.md
│   ├── database-backends.md
│   └── troubleshooting.md
└── scripts/
    └── check_prereqs.py
```

## Installing this skill

### Claude Code

Copy or clone the `skills/eahelper` folder into your Claude Code skills directory.

**Personal (all projects), macOS/Linux:**

```bash
mkdir -p ~/.claude/skills
cp -R skills/eahelper ~/.claude/skills/eahelper
```

**Personal (all projects), Windows (PowerShell):**

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse -Force "skills\eahelper" "$env:USERPROFILE\.claude\skills\eahelper"
```

**Project-scoped (this repo only), any OS:**

```bash
mkdir -p .claude/skills
cp -R /path/to/dvm-eahelper-skills/skills/eahelper .claude/skills/eahelper
```

Or clone this whole repo directly into place instead of copying:

```bash
git clone <this-repo-url> ~/.claude/skills/dvm-eahelper-skills
# then symlink or copy just the skill folder in, e.g.:
ln -s ~/.claude/skills/dvm-eahelper-skills/skills/eahelper ~/.claude/skills/eahelper
```

Claude Code picks up skills automatically from `~/.claude/skills` (personal) and `.claude/skills`
(project) — no restart or registration step beyond placing the folder.

### GitHub Copilot (VS Code)

Per the [GitHub Copilot Agent Skills docs](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills),
Copilot follows the same open Agent Skills standard and looks for skills in:

- **Repository-level**, any of: `.github/skills/`, `.claude/skills/`, `.agents/skills/`
- **Personal/global**: `~/.copilot/skills/` or `~/.agents/skills/`

**Repository-level (recommended for a team working in a shared repo), macOS/Linux:**

```bash
mkdir -p .github/skills
cp -R skills/eahelper .github/skills/eahelper
```

**Repository-level, Windows (PowerShell):**

```powershell
New-Item -ItemType Directory -Force -Path ".github\skills" | Out-Null
Copy-Item -Recurse -Force "skills\eahelper" ".github\skills\eahelper"
```

**Personal/global, macOS/Linux:**

```bash
mkdir -p ~/.copilot/skills
cp -R skills/eahelper ~/.copilot/skills/eahelper
```

**Personal/global, Windows (PowerShell):**

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.copilot\skills" | Out-Null
Copy-Item -Recurse -Force "skills\eahelper" "$env:USERPROFILE\.copilot\skills\eahelper"
```

Commit the `.github/skills/eahelper` folder to share the skill with everyone working in that
repository via Copilot in VS Code.

> Verify against the current docs before relying on this: GitHub's Agent Skills feature is
> evolving, and the exact supported paths/behavior may change. See
> <https://docs.github.com/en/copilot/concepts/agents/about-agent-skills>.

## What the skill covers

1. Installing `dvm-eahelper` with `uv` (`uv tool install dvm-eahelper` or `uvx dvm-eahelper`) and
   the one-time Playwright Chromium setup.
2. Starting the integrated supervisor, `eahelper server` — GraphQL proxy (port 8765) + embedded
   MCP endpoint (`/mcp`) + a managed debug browser (CDP port 19222, persistent profile). First run
   prompts for the LeanIX workspace URL and database choice and saves them to
   `~/.eahelper/config.toml`; the managed browser opens for login and **closes itself
   automatically** once a token is captured. `server start|stop|status` run it as a background
   daemon (pidfile + `server.log` under `~/.eahelper/`).
3. Downloading factsheets (`eahelper download`) and loading them into KuzuDB or Neo4j
   (`eahelper load --db kuzu|neo4j`), or loading a demo graph (`eahelper seed`) — both `download`
   and `load` auto-start the server in the background if it isn't already running, so a second
   terminal is no longer required.
4. Querying the graph over the embedded MCP endpoint — the same `get_schema`/`query` tools work
   for both KuzuDB and Neo4j. Run `eahelper mcp-config --install` to wire up Claude Code
   (`.mcp.json`) and/or VS Code/Copilot (`.vscode/mcp.json`), offering both the HTTP endpoint and a
   stdio variant (`eahelper mcp`). External Kuzu/Neo4j MCP servers remain documented as fallbacks.
5. Managing persisted settings via `eahelper config` (`~/.eahelper/config.toml`) — CLI flag > env
   var > config.toml > interactive prompt, with prompts saved back so the user is asked once ever.
   Passwords (e.g. `NEO4J_PASSWORD`) are never stored in the config file.
6. Troubleshooting the common failure points: CDP port 19222 conflicts, Edge on Windows requiring
   all windows closed first, KuzuDB's single-writer lock conflicting between the server's MCP
   endpoint and a concurrent `load`, stale pidfiles, token extraction timeouts, corporate
   SSL-inspection proxies, and Neo4j connection/auth issues.

## License

MIT — see [LICENSE](LICENSE).
