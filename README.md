# dvm-eahelper-skills

An [Agent Skill](https://agentskills.io) that teaches AI coding agents (Claude Code, GitHub
Copilot) how to work with the [`dvm-eahelper`](https://pypi.org/project/dvm-eahelper/) Python
package for SAP LeanIX — installing it, running its local GraphQL proxy against an
already-logged-in browser, downloading factsheets, loading them into a graph database (KuzuDB by
default, or Neo4j), and querying the result.

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
2. Launching an isolated, CDP-debuggable Chrome/Edge instance on port 9222 (Windows and macOS
   commands) and logging in to LeanIX in it.
3. Starting the local GraphQL proxy (`eahelper proxy`), downloading factsheets
   (`eahelper download`), and loading them into KuzuDB or Neo4j (`eahelper load --db kuzu|neo4j`),
   or loading a demo graph (`eahelper seed`).
4. Querying the graph — directly via the `kuzu` Python API or a Kuzu MCP server, or via the
   `mcp-neo4j-cypher` MCP server for Neo4j.
5. Troubleshooting the common failure points: the debug port not opening, token extraction
   timeouts, running `download`/`load` before the proxy is up, corporate SSL-inspection proxies,
   and Neo4j connection/auth issues.

## License

MIT — see [LICENSE](LICENSE).
