# Common Patterns

## Composite backend routing `/memories/`

The canonical pattern for "some paths must survive across threads, everything else is
scratch-space" is `CompositeBackend` routing a `/memories/` prefix to `StoreBackend` while leaving
the default backend ephemeral (`StateBackend`). Longer path prefixes take precedence when multiple
routes could match.

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/memories/": StoreBackend(namespace=lambda _rt: ("memories",)),
        },
    ),
    store=InMemoryStore(),  # store goes to create_deep_agent, not the backend constructor
)
```

Swap `InMemoryStore()` for a persistent LangGraph store (e.g. a Postgres-backed store) in
production — `InMemoryStore` loses everything on process restart. For multi-user isolation, make
the namespace factory a function of the request's identity rather than a fixed tuple, e.g.
`namespace=lambda rt: (rt.server_info.user.identity,)`.

## Memory scoping

Two scoping strategies for `memory=` / `AGENTS.md` files, from the memory doc:

- **Agent-scoped**: all users share namespace `(assistant_id,)`. Gives the agent one persistent,
  evolving identity/persona/knowledge base across every user. Use when the memory content is
  genuinely shared policy or product knowledge, not user-specific.
- **User-scoped**: each user gets an isolated namespace `(user_id,)`. Prevents information leakage
  between users and is the safer default.

Security note from the docs, verbatim in spirit: if one user can write to memory that another user
reads, a malicious user can inject instructions into shared state. Mitigations: default to
user-scoped memory, make shared/agent-scoped memory read-only for the model, and require human
approval (`interrupt_on={"edit_file": True}`) for writes to anything memory-related that isn't
strictly per-user.

An optional background-consolidation pattern: run a separate agent between user interactions that
synthesizes conversation history into memory, keeping active-conversation latency low while still
improving memory quality asynchronously.

## Read-only vs. read-write tool restriction

Two independent levers:

1. **Hide filesystem tools from the model entirely** via a harness profile's `excluded_tools` (you
   cannot remove `FilesystemMiddleware` itself — only the model-visible tool surface):

```python
from deepagents import HarnessProfile, register_harness_profile

register_harness_profile(
    "anthropic:claude-sonnet-4-6",
    HarnessProfile(
        excluded_tools=frozenset(
            {"ls", "read_file", "write_file", "edit_file", "delete", "glob", "grep"}
        ),
    ),
)
```

2. **Allowlist a subset** via `FilesystemMiddleware(tools=[...])` (requires `deepagents>=0.7.0a4`)
   — everything left out is removed from both the model's tool list and the middleware's dynamic
   system-prompt section. `read_file` must always be included or agent creation raises `ValueError`.

```python
from deepagents import create_deep_agent
from deepagents.middleware import FilesystemMiddleware

# Read-only agent: write_file, edit_file, delete, and execute are never shown
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    middleware=[
        FilesystemMiddleware(backend=backend, tools=["read_file", "ls", "glob", "grep"]),
    ],
)
```

Passing your own `FilesystemMiddleware` instance this way replaces the default one for the main
agent, and the auto-added `general-purpose` subagent inherits the same restriction. Custom,
explicitly-named subagents do **not** inherit it automatically — give each its own
`FilesystemMiddleware(tools=[...])` instance in that subagent's `middleware=` list if you need it
restricted independently.

For a strict allow/deny-by-path model instead of an allow/deny-by-tool-name model, use
`permissions=[...]` (see [api-reference.md](api-reference.md#filesystem-permissions)) — the two
mechanisms are complementary: `tools=` controls *which operations exist at all*, `permissions=`
controls *which paths* an existing operation may touch. Note `permissions=` does not constrain
sandbox `execute`.

## Sandbox selection

Two integration patterns, per the sandboxes doc:

- **Agent-in-sandbox**: the agent process itself runs inside the sandbox and you talk to it over
  the network. Mirrors local dev closely, but every code change needs an image rebuild.
- **Sandbox-as-tool** (recommended for most use cases per the docs): the agent runs externally
  (e.g. on your own server) and calls sandbox operations through the provider's API/backend
  integration. Lets you iterate on agent code instantly, keeps API keys outside the sandbox, and
  supports running many sandboxes in parallel for concurrent tasks — at the cost of added network
  latency per sandbox call.

Providers referenced across the docs: LangSmith-managed sandboxes, Daytona (has native git
operations), E2B, Modal, Runloop, Vercel, AgentCore, NVIDIA OpenShell. Each needs its own
`langchain-*` integration package and provider credentials/auth — the fetched pages did not include
a single canonical "select provider via one environment variable" mechanism common to all of them,
so treat any such env-var switch as **provider-specific and unverified** here; check the specific
provider's integration page before assuming a generic `DEEPAGENTS_SANDBOX=<provider>` toggle
exists.

Verified Daytona example:

```python
sandbox = Daytona().create()
backend = DaytonaSandbox(sandbox=sandbox)

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are a Python coding assistant with sandbox access.",
    backend=backend,
)
```

Regardless of provider: never inject real secrets into the sandbox environment — a
context-injected agent can read and exfiltrate them. Keep credentials in tools/proxies the agent
calls, not in the sandbox's own environment variables or filesystem.

## FastAPI wrapper

A minimal pattern for exposing a deep agent behind an HTTP endpoint outside of `langgraph dev` /
LangSmith Deployment. This is not lifted verbatim from the docs (the fetched pages did not include
a FastAPI example) — it follows standard LangGraph/FastAPI async-invoke conventions and should be
adapted to your own auth/streaming needs before treating it as production-ready:

```python
from fastapi import FastAPI
from pydantic import BaseModel
from deepagents import create_deep_agent

app = FastAPI()

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are a helpful assistant",
)


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


@app.post("/chat")
async def chat(req: ChatRequest):
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": req.message}]},
        config={"configurable": {"thread_id": req.thread_id}},
    )
    return {"reply": result["messages"][-1].content}
```

## CLI REPL loop

Also not sourced verbatim from the docs — a plain interactive loop around `agent.invoke`, useful
for quick manual testing before wiring up `langgraph dev` or a web frontend:

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are a helpful assistant",
)

thread_id = "repl-session"
print("Type 'exit' to quit.")
while True:
    user_input = input("> ")
    if user_input.strip().lower() in {"exit", "quit"}:
        break
    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    print(result["messages"][-1].content)
```

## `langgraph.json` layout

For local dev via `langgraph dev` (LangGraph Studio) or LangSmith Deployment, register the
compiled agent(s) in a `langgraph.json` at the project root:

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./agent.py:agent"
  },
  "env": ".env"
}
```

| Field | Purpose |
|---|---|
| `dependencies` | Packages to install; `["."]` installs the current directory as a package |
| `graphs` | Maps a graph id to `"<id>": "./<file>:<variable>"`, where `<variable>` is the compiled graph or constructor function exported from `<file>` |
| `env` | Path to an env file with API keys/secrets |

If you have multiple graphs that should be co-deployed (e.g. a supervisor plus separately-defined
subagent graphs built as `CompiledSubAgent`s), list them all under `graphs`:

```json
{
  "graphs": {
    "supervisor": "./src/supervisor.py:graph",
    "researcher": "./src/researcher.py:graph",
    "coder": "./src/coder.py:graph"
  }
}
```

Run locally:

```bash
pip install -U "langgraph-cli[inmem]"
langgraph dev
```

```powershell
pip install -U "langgraph-cli[inmem]"
langgraph dev
```

The fetched "Going to production" doc mentions `langgraph dev` for local testing but does not show
its CLI flags — use `langgraph dev --help` for authoritative flag documentation. Production
deployment paths mentioned in the docs: **Managed Deep Agents** (a CLI-first hosted runtime for
deep agents specifically, in private preview at time of writing) or a standard **LangSmith
Deployment** using the same `langgraph.json`.
