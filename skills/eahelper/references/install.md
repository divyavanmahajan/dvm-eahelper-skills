# Install Reference

## Requirements

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | [python.org/downloads](https://www.python.org/downloads/) |
| `uv` | any recent | Package/tool manager used to install and run `dvm-eahelper` |
| Google Chrome or Microsoft Edge | any recent | Needed for browser-based token extraction (skip if using a Technical User API key) |
| Neo4j Desktop | 5.x | Only needed if using `--db neo4j` |

KuzuDB needs **no separate install** — it is an embedded database bundled as a Python dependency
of `dvm-eahelper`; the graph is a local file on disk.

## Install `uv`

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify:

```bash
uv --version
```

## Install `dvm-eahelper`

Two supported ways to run it:

### Option A — install as a uv tool (recommended for repeated use)

```bash
uv tool install dvm-eahelper
```

This puts `eahelper` on your `PATH`. Upgrade later with:

```bash
uv tool upgrade dvm-eahelper
```

### Option B — run without installing, via `uvx`

```bash
uvx dvm-eahelper -- proxy
uvx dvm-eahelper -- download --list-types
```

Everything after `--` is passed straight to `eahelper`.

## Install Playwright's Chromium binary (one-time)

`eahelper server` uses Playwright to launch and attach to the managed debug browser over CDP.
Playwright needs its own bundled Chromium **runtime files** for this even when the managed browser
itself is Chrome or Edge — install once:

```bash
# If eahelper is installed as a uv tool:
uv tool run --from dvm-eahelper playwright install chromium

# If using uvx:
uvx --from dvm-eahelper playwright install chromium
```

If this step is skipped, `eahelper server` may fail with a Playwright "executable doesn't exist"
error the first time it tries to launch the managed browser.

## Configuration file: `~/.eahelper/config.toml`

`eahelper` persists resolved settings (workspace URL, preferred browser/CDP port, default graph
backend, Neo4j URI, etc.) to `~/.eahelper/config.toml` the first time they're supplied — either via
a CLI flag or an interactive prompt. On every later run, the stored value is reused automatically,
so setup questions (workspace URL, kuzu vs. neo4j) are normally asked at most once per machine.
Passwords are never written here (`NEO4J_PASSWORD` always comes from an environment variable or
`.env`). See [cli-reference.md](cli-reference.md#eahelper-config) for the `eahelper config`
subcommand and the full list of recognized keys, and
[browser-setup.md](browser-setup.md) for the managed-browser profile directory
(`~/.eahelper/browser-profile`) that lives alongside it.

## Verifying the install

```bash
eahelper --help
eahelper server --help
python3 --version   # or `python --version` on Windows
uv --version
```

Or run the bundled prerequisite checker (works identically on Windows and macOS):

```bash
python scripts/check_prereqs.py
```

It reports, in order: Python version, `uv` presence, `dvm-eahelper` installation, Playwright
Chromium install status, whether `~/.eahelper/config.toml` exists yet, whether the managed-browser
CDP port (`19222`) is currently reachable (informational only — it's expected to be closed unless
`eahelper server` is mid-login), and whether the `eahelper server` health endpoint
(`http://localhost:8765/healthz`) is currently responding.
