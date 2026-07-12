# dvm-eahelper-skills

[Agent Skills](https://agentskills.io) that teach AI coding agents (Claude Code, GitHub Copilot)
specialized workflows. This repo contains **two skills**, each following the open Agent Skills
standard: a folder with a `SKILL.md` (YAML frontmatter + markdown instructions), plus
`references/` for detail the agent pulls in on demand.

1. **`eahelper`** — work with the [`dvm-eahelper`](https://pypi.org/project/dvm-eahelper/) Python
   package for SAP LeanIX: installing it, running its integrated server (GraphQL proxy + embedded
   MCP endpoint + managed debug browser), downloading factsheets, loading them into a graph
   database (KuzuDB by default, or Neo4j), and querying the result over MCP.
2. **`deepagents`** — implement agents with the LangChain
   [DeepAgents](https://docs.langchain.com/oss/python/deepagents/overview) Python framework
   (PyPI package [`deepagents`](https://pypi.org/project/deepagents/)): `create_deep_agent`,
   filesystem backends and sandboxes, tool/MCP registration, agentskills.io-format skill
   directories, `AGENTS.md` memory, subagents, model provider strings (incl. Azure OpenAI and
   LiteLLM-style gateways), running locally with `langgraph dev`, and serving over HTTP (AG-UI
   protocol, Azure AI Foundry hosted agents, OpenTelemetry).

```
skills/
├── eahelper/
│   ├── SKILL.md
│   ├── references/
│   │   ├── install.md
│   │   ├── browser-setup.md
│   │   ├── cli-reference.md
│   │   ├── database-backends.md
│   │   └── troubleshooting.md
│   └── scripts/
│       └── check_prereqs.py
└── deepagents/
    ├── SKILL.md
    └── references/
        ├── api-reference.md
        ├── patterns.md
        └── serving.md
```

## Installing the skills

The commands below show the `eahelper` skill; to install the `deepagents` skill (or both), repeat
the same copy command with `skills/deepagents` as the source and `deepagents` as the target folder
name — e.g. `cp -R skills/deepagents ~/.claude/skills/deepagents`.

### Claude Code

Copy or clone the skill folder(s) into your Claude Code skills directory.

**Personal (all projects), macOS/Linux:**

```bash
mkdir -p ~/.claude/skills
cp -R skills/eahelper ~/.claude/skills/eahelper
cp -R skills/deepagents ~/.claude/skills/deepagents
```

**Personal (all projects), Windows (PowerShell):**

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse -Force "skills\eahelper" "$env:USERPROFILE\.claude\skills\eahelper"
Copy-Item -Recurse -Force "skills\deepagents" "$env:USERPROFILE\.claude\skills\deepagents"
```

**Project-scoped (this repo only), any OS:**

```bash
mkdir -p .claude/skills
cp -R /path/to/dvm-eahelper-skills/skills/eahelper .claude/skills/eahelper
cp -R /path/to/dvm-eahelper-skills/skills/deepagents .claude/skills/deepagents
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
cp -R skills/deepagents .github/skills/deepagents
```

**Repository-level, Windows (PowerShell):**

```powershell
New-Item -ItemType Directory -Force -Path ".github\skills" | Out-Null
Copy-Item -Recurse -Force "skills\eahelper" ".github\skills\eahelper"
Copy-Item -Recurse -Force "skills\deepagents" ".github\skills\deepagents"
```

**Personal/global, macOS/Linux:**

```bash
mkdir -p ~/.copilot/skills
cp -R skills/eahelper ~/.copilot/skills/eahelper
cp -R skills/deepagents ~/.copilot/skills/deepagents
```

**Personal/global, Windows (PowerShell):**

```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.copilot\skills" | Out-Null
Copy-Item -Recurse -Force "skills\eahelper" "$env:USERPROFILE\.copilot\skills\eahelper"
Copy-Item -Recurse -Force "skills\deepagents" "$env:USERPROFILE\.copilot\skills\deepagents"
```

Commit the `.github/skills/eahelper` and/or `.github/skills/deepagents` folders to share the
skills with everyone working in that repository via Copilot in VS Code.

> Verify against the current docs before relying on this: GitHub's Agent Skills feature is
> evolving, and the exact supported paths/behavior may change. See
> <https://docs.github.com/en/copilot/concepts/agents/about-agent-skills>.

## What the `eahelper` skill covers

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

## What the `deepagents` skill covers

1. Installing the [`deepagents`](https://pypi.org/project/deepagents/) package (Python >=3.11) and
   creating a minimal agent with `create_deep_agent`.
2. Choosing a virtual filesystem backend — `StateBackend` (default), `FilesystemBackend`,
   `StoreBackend`, `ContextHubBackend`, `CompositeBackend` routing (e.g. persistent `/memories/`),
   `LocalShellBackend` (dev-only, with explicit warnings), and sandbox backends (Daytona, E2B,
   Modal, Runloop, Vercel, AgentCore, NVIDIA OpenShell, LangSmith-managed).
3. Registering tools: plain Python functions, LangChain tools, and MCP servers via
   `langchain-mcp-adapters`.
4. Skills directories (agentskills.io spec, same standard as this repo) and `AGENTS.md` memory,
   including scoping and prompt-injection considerations.
5. Model provider strings — Anthropic, OpenAI, Google, OpenRouter, Fireworks, Baseten, Ollama —
   plus Azure OpenAI (`azure_openai:` with `azure_deployment`) and OpenAI-compatible gateways
   (LiteLLM proxy via `init_chat_model(..., base_url=...)`).
6. Subagents (`SubAgent` dicts, `CompiledSubAgent`, the default `general-purpose` subagent) and
   running locally with `langgraph.json` + `langgraph dev`, or a FastAPI wrapper / CLI REPL.
7. Serving the agent over HTTP: an AG-UI protocol endpoint (`ag-ui-langgraph`, with a
   RUN_ERROR-guarding wrapper and `@ag-ui/client` testing), Azure AI Foundry hosted agents
   (`azure-ai-agentserver-langgraph`, matching-prerelease version pins, the
   `/runs`/`/responses`/probe contract), a hand-rolled OpenAI-Responses-shape endpoint for local
   testing, and env-var-driven OpenTelemetry tracing — all verified against a working
   implementation.

## License

MIT — see [LICENSE](LICENSE).
