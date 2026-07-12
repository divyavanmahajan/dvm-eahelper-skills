---
name: deepagents
description: Build or modify AI agents with the LangChain DeepAgents Python framework (PyPI package `deepagents`) - create_deep_agent, filesystem backends (State/Filesystem/Store/Composite/LocalShell/sandboxes), tool and MCP registration, agentskills.io-format skills directories, AGENTS.md memory, subagents, model provider strings (Anthropic, OpenAI, Azure OpenAI, OpenRouter, LiteLLM gateways, Ollama), running locally with langgraph dev, and serving over HTTP (AG-UI protocol endpoint, Azure AI Foundry hosted agent, OpenAI-Responses-shape endpoint, OpenTelemetry tracing).
---

# deepagents — LangChain DeepAgents Framework

[`deepagents`](https://pypi.org/project/deepagents/) (current PyPI version **0.6.12**, requires
**Python >=3.11, <4.0**) is a standalone library built on LangChain/LangGraph that gives an agent
a built-in harness: task planning, a virtual filesystem, subagent delegation, skills, and
persistent memory — on top of the same tool-calling loop as other agent frameworks.

Use this skill whenever the user wants to build a new DeepAgents-based agent, add tools/subagents
to one, choose a filesystem backend, wire up skills or memory, or pick a model provider string.

Full detail for each topic lives in `references/`; pull those in only when you need more than the
summary below.

## 1. Install

```bash
# macOS / Linux
pip install deepagents
# or with uv
uv add deepagents
```

```powershell
# Windows (PowerShell) — identical, pip/uv work the same
pip install deepagents
uv add deepagents
```

For dynamic (code-driven) subagent dispatch you additionally need the QuickJS interpreter extra:
`pip install -U "deepagents[quickjs]"` (needs `langchain-quickjs>=0.2.0`).

## 2. Minimal agent

```python
from deepagents import create_deep_agent


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"


agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)

agent.invoke({"messages": [{"role": "user", "content": "what is the weather in sf"}]})
```

`create_deep_agent` is the entry point for everything else in this skill — model, tools, memory,
skills, backend, subagents, permissions, and human-in-the-loop all thread through it. See
[references/api-reference.md](references/api-reference.md) for the parameter list and the default
middleware stack (order matters: TodoList → Skills → Filesystem → SubAgent → Summarization →
PatchToolCalls → AsyncSubAgent → your middleware → profile → prompt-caching → Memory →
HumanInTheLoop).

Every agent gets built-in filesystem tools for free — `ls`, `read_file`, `write_file`,
`edit_file`, `delete`, `glob`, `grep` — plus `write_todos` for task planning and `task` for
subagent delegation. `execute` (shell) is only added when the backend supports it (sandbox
backends, or `LocalShellBackend`). See the filesystem tool table in
[references/api-reference.md](references/api-reference.md).

## 3. Choosing a backend

The virtual filesystem the agent sees is backed by a pluggable **backend**, passed via `backend=`.
Default is `StateBackend` (in-memory, thread-scoped) if you pass nothing.

| Backend | Scope | Use for |
|---|---|---|
| `StateBackend` (default) | Thread-scoped, in LangGraph state | Agent scratch pad, intermediate results |
| `FilesystemBackend` | Local disk | Local development, CI/CD — needs `virtual_mode=True` for path sandboxing |
| `StoreBackend` | Cross-thread persistent (LangGraph `BaseStore`) | Long-term memory, multi-user isolation via namespace factory |
| `ContextHubBackend` | LangSmith Hub repos | Durable storage without standing up a separate store |
| `CompositeBackend` | Routes by path prefix to other backends | e.g. `/memories/` → `StoreBackend`, everything else ephemeral |
| `LocalShellBackend` | Host system (real disk + shell) | **Dev-only.** Local CLIs you trust — see warning below |
| Sandbox backends (Daytona, E2B, Modal, Runloop, Vercel, AgentCore, NVIDIA OpenShell, LangSmith-managed) | Isolated remote/container environment | Secure code execution, untrusted input, production shell access |

**`LocalShellBackend` and running without a sandbox at all are dev-only postures.**
`LocalShellBackend` "grants agents direct filesystem read/write access **and** unrestricted shell
execution on your host" — appropriate for local dev CLIs and CI with proper secret handling, **not**
for production web servers, multi-tenant systems, or untrusted input. For anything
production-facing or handling untrusted input, use a sandbox backend instead. **Never put secrets
inside a sandbox either** — credentials injected into a sandbox can be read/exfiltrated by a
context-injected agent; keep secrets in external tools or a proxy that injects them without
exposing them to the model.

Filesystem **permissions** (`permissions=` — allow/deny rules over `read`/`write` operations on
glob path patterns, first-match-wins) apply to backend filesystem tools but **not** to sandbox
`execute` — sandboxes need backend-level policy hooks instead.

Verbatim constructor snippets, the `CompositeBackend` routing pattern, and the custom
`BackendProtocol` method list are in
[references/api-reference.md](references/api-reference.md#backends). Sandbox provider notes and
the agent-in-sandbox vs. sandbox-as-tool tradeoff are in
[references/patterns.md](references/patterns.md#sandbox-selection).

## 4. Registering tools (plain functions + MCP)

Plain Python functions work directly — pass them via `tools=[...]`; DeepAgents infers the schema
from the signature and docstring (write a real docstring — it becomes the tool description the
model sees). LangChain `@tool`-decorated functions and tool dicts also work. Prefer tools that
return error strings/JSON over tools that raise, so the agent can recover.

For MCP servers, install `langchain-mcp-adapters` and use `MultiServerMCPClient`. One client can
mix **stdio** (local server process) and **HTTP** (running server) transports; `get_tools()` is
async, so build the agent inside an async entry point:

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from deepagents import create_deep_agent


async def main():
    client = MultiServerMCPClient(
        {
            # stdio: spawn a local server process
            "math": {
                "transport": "stdio",
                "command": "python",
                "args": ["/path/to/math_server.py"],
            },
            # streamable HTTP: connect to a running server
            "my_server": {
                "transport": "http",
                "url": "http://localhost:8000/mcp",
            },
        }
    )
    tools = await client.get_tools()   # LangChain tools from ALL configured servers

    agent = create_deep_agent(model="anthropic:claude-sonnet-4-6", tools=tools)

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Use the MCP server to help me."}]},
        config={"configurable": {"thread_id": "1"}},
    )


asyncio.run(main())
```

MCP tools and plain functions can be combined in the same `tools=[...]` list. The tools doc also
mentions OAuth auth and MCP tool filtering — see the caveat in
[references/api-reference.md](references/api-reference.md#mcp-tools) before relying on exact
parameter names for those.

## 5. Skills directories (agentskills.io spec)

DeepAgents skills follow the same open [Agent Skills standard](https://agentskills.io/) this repo
already uses for `eahelper` itself. To **author** a new skill:

1. Create a top-level skills *source directory* (e.g. `skills/`) containing **one subdirectory per
   skill** — `skills=` takes source directories, not individual skill paths (verified in working
   code: `skills=["/skills/"]` with `/skills/my-skill/SKILL.md` inside).
2. In each skill subdirectory, create `SKILL.md` with YAML frontmatter — `name` and `description`
   are required (the spec also defines optional `license`, compatibility, and metadata fields):

   ```markdown
   ---
   name: my-skill
   description: What this does and WHEN the agent should use it (the trigger).
   ---

   # my-skill

   Markdown instructions for the agent...
   ```

3. Optionally add `scripts/`, `references/`, `assets/` and point to them with relative paths from
   the skill root; avoid deeply nested reference chains.
4. Register the source dir(s) on the agent:

```python
agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    skills=["./project/skills/"],
)
```

**Progressive loading** (why this structure matters): (1) frontmatter of every configured skill is
loaded at startup — descriptions must carry the "when to activate" signal; (2) the full `SKILL.md`
body is loaded only when the agent decides the skill applies; (3) supporting files are read only
as the instructions reference them. Keep each `SKILL.md` under ~5,000 tokens / 500 lines,
consolidate overlapping skills rather than multiplying similar ones, and note DeepAgents enforces
a 10 MB file-size limit during skill discovery.

The general-purpose subagent automatically inherits the main agent's skills; custom subagents do
**not** inherit skills by default and need their own `skills=[...]` (their skill state is fully
isolated from the parent in both directions).

## 6. Memory (`AGENTS.md`)

Memory gives an agent persistent context — coding style, preferences, project conventions — across
conversations, using [`AGENTS.md`](https://agents.md/) files passed via `memory=`. Unlike skills,
memory content is **always** loaded into the system prompt, and is stored in whichever backend the
agent uses (`StateBackend`, `StoreBackend`, or `FilesystemBackend`). When you pass `memory=`, you
must add the expected memory files to the backend before creating the agent.

```markdown
## Response style
- Keep responses concise
- Use code examples where possible
```

Scope memory per-agent (shared namespace `(assistant_id,)` — one evolving persona for everyone) or
per-user (`(user_id,)` — isolated per user, prevents cross-user prompt injection via shared writes).
Prefer user-scoped memory by default and read-only access for anything agent-wide/shared. See
[references/patterns.md](references/patterns.md#memory-scoping) for the tradeoffs.

## 7. Model provider strings

`model=` takes a `"provider:model"` string (via `init_chat_model` under the hood) or a LangChain
chat model instance. Examples seen across the docs:

| Provider | Example string |
|---|---|
| Anthropic | `"anthropic:claude-sonnet-4-6"` |
| OpenAI | `"openai:gpt-5.5"` |
| Google Gemini | `"google_genai:gemini-3.5-flash"` |
| OpenRouter | `"openrouter:z-ai/glm-5.2"` |
| Fireworks | `"fireworks:accounts/fireworks/models/glm-5p2"` |
| Baseten | `"baseten:zai-org/GLM-5.2"` |
| Ollama | `"ollama:north-mini-code-1.0"` |
| Azure OpenAI | `"azure_openai:gpt-5.5"` (needs `azure_deployment=` kwarg — see below) |

**Azure OpenAI** needs the deployment name passed explicitly and two env vars:

```python
import os
from deepagents import create_deep_agent

os.environ["AZURE_OPENAI_API_KEY"] = "..."
os.environ["AZURE_OPENAI_ENDPOINT"] = "..."

agent = create_deep_agent(
    model="azure_openai:gpt-5.5",
    ...
)
# The model string alone is not sufficient for Azure — pass azure_deployment via
# init_chat_model / AzureChatOpenAI directly when create_deep_agent's string form
# doesn't expose it; see references/api-reference.md#model-strings for both forms.
```

**Gateway / OpenAI-compatible endpoints (e.g. an internal LiteLLM proxy, Together AI, vLLM)**: use
`init_chat_model` directly with `model_provider="openai"` and `base_url=`, then pass the resulting
model object as `model=` to `create_deep_agent` — the docs explicitly warn that `base_url` here
only works for endpoints implementing the official OpenAI Chat Completions spec, and recommend the
dedicated `langchain-litellm` (`ChatLiteLLM`/`ChatLiteLLMRouter`) or `langchain-openrouter`
integrations instead of generic `base_url` routing when you specifically mean LiteLLM/OpenRouter:

```python
from langchain.chat_models import init_chat_model
from deepagents import create_deep_agent

model = init_chat_model(
    model="MODEL_NAME",
    model_provider="openai",
    base_url="BASE_URL",     # e.g. your LiteLLM proxy's OpenAI-compatible endpoint
    api_key="YOUR_API_KEY",
)

agent = create_deep_agent(model=model, ...)
```

See [references/api-reference.md](references/api-reference.md#model-strings) for the full set of
verified snippets and the LiteLLM/OpenRouter caveat verbatim.

## 8. Subagents

Subagents solve **context bloat**: heavy multi-step work (web searches, big file reads, DB
queries) runs in an isolated child context, and the main agent receives only the final report via
the built-in `task` tool. Use them for multi-step tasks that would clutter the main context,
specialized domains needing their own instructions/tools, or tasks wanting a different model.
Skip them for simple single-step tasks, when intermediate context must be preserved, or when the
delegation overhead outweighs the benefit.

Pass `subagents=[...]` — a list of `SubAgent` dicts (`name`, `description`, `system_prompt`
required; optional `tools`, `model`, `middleware`, `interrupt_on`, `skills`, `response_format`,
`permissions`) or `CompiledSubAgent` objects wrapping a prebuilt LangGraph graph (any
`.compile()`d graph with a `"messages"` state key, e.g. from `langchain.agents.create_agent`).
Key inheritance rules: `system_prompt` and `skills` do **not** inherit from the main agent;
`tools`, `model`, `interrupt_on`, and `permissions` inherit unless overridden (`tools`/`permissions`
override *entirely* when set). Complete example:

```python
from deepagents import create_deep_agent


def internet_search(query: str) -> str:
    """Run a web search."""
    return f"search results for {query}"


research_subagent = {
    "name": "research-agent",
    "description": "Used to research more in depth questions",   # drives the delegation decision
    "system_prompt": "You are a great researcher",
    "tools": [internet_search],
    "model": "openai:gpt-5.5",  # optional override, defaults to main agent model
}

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    subagents=[research_subagent],
)

agent.invoke({"messages": [{"role": "user", "content": "Research recent advances in quantum computing"}]})
```

Write `description` action-oriented and specific — the main agent chooses subagents by it. Add
`response_format` (a Pydantic model; `deepagents>=0.5.3`) when the parent must parse the result as
JSON instead of free text.

A `general-purpose` subagent is added automatically unless you supply your own with that exact
name; it inherits the main agent's skills, tools, and model. To disable subagents/the `task` tool
entirely, set `general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)` on the
harness profile **and** pass no synchronous `subagents=` — do not try to remove
`SubAgentMiddleware` via `excluded_middleware` (rejected with `ValueError`). Full field table and
the `CompiledSubAgent` example are in
[references/api-reference.md](references/api-reference.md#subagents).

## 9. Running locally with `langgraph dev`

For local iteration and the LangGraph Studio UI, expose the compiled agent through a
`langgraph.json` at the project root and run the LangGraph CLI dev server:

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./agent.py:agent"
  },
  "env": ".env"
}
```

```bash
# macOS / Linux
pip install -U "langgraph-cli[inmem]"
langgraph dev
```

```powershell
# Windows (PowerShell)
pip install -U "langgraph-cli[inmem]"
langgraph dev
```

`"agent.py:agent"` means "the `agent` object exported from `agent.py`" — point it at wherever your
`create_deep_agent(...)` call lives. `dependencies: ["."]` installs the current project as a
package so `langgraph dev` can import it. Multiple graphs (e.g. supervisor + subagent graphs
deployed together) can be listed side by side under `graphs`. See
[references/patterns.md](references/patterns.md#langgraphjson-layout) for a fuller example and a
FastAPI-wrapper / CLI REPL alternative to `langgraph dev` for non-Studio use.

> The docs describe `langgraph dev` as the local-development path but don't spell out every CLI
> flag in the pages fetched for this skill — treat `langgraph dev --help` as authoritative for
> flags beyond the basic invocation above.

**Checkpointer rule of thumb:** build the graph with `checkpointer=None` for `langgraph dev` /
LangGraph platform (they inject their own persistence), but with an explicit checkpointer (e.g.
`InMemorySaver()`) when self-hosting — the AG-UI and Azure Foundry adapters in
[references/serving.md](references/serving.md) require one.

## 10. Serving over HTTP (AG-UI, Azure AI Foundry, OpenTelemetry)

To expose the agent beyond `langgraph dev`, see
[references/serving.md](references/serving.md) — all verified against a working implementation:

- **AG-UI protocol** (`ag-ui-langgraph`: `LangGraphAgent` + `add_langgraph_fastapi_endpoint`) for
  CopilotKit/AG-UI frontends — including the required checkpointer, a RUN_ERROR-guarding wrapper
  (the official endpoint drops the socket on mid-run exceptions), a
  `from __future__ import annotations` + FastAPI forward-ref pitfall, and testing with
  `@ag-ui/client`'s `HttpAgent`.
- **Azure AI Foundry hosted agent** (`azure-ai-agentserver-langgraph` +
  `azure-ai-agentserver-core`, pinned to *matching* prerelease versions — skew breaks imports):
  `from_langgraph(graph).run()`, port 8088 / `DEFAULT_AD_PORT`, the
  `/runs` `/responses` `/liveness` `/readiness` contract, the `AZURE_AI_PROJECT_ENDPOINT`
  requirement, and a hand-rolled OpenAI-Responses-shape endpoint for local testing without Azure.
- **OpenTelemetry**: env-var-driven, no-op-by-default tracing (`OTEL_EXPORTER_OTLP_ENDPOINT`,
  `OTEL_TRACES_EXPORTER`, `OTEL_SERVICE_NAME`, `OTEL_SDK_DISABLED`), FastAPI instrumentation, and
  `opentelemetry-instrumentation-langchain` for LLM/chain spans.

## Reference index

- [references/api-reference.md](references/api-reference.md) — `create_deep_agent` parameters,
  backend classes with verbatim constructor snippets, built-in filesystem tool list, model-string
  forms, subagent field table, MCP config shapes.
- [references/patterns.md](references/patterns.md) — composite backend `/memories/` routing,
  read-only vs. read-write tool restriction, sandbox provider selection, FastAPI wrapper, CLI REPL
  loop, `langgraph.json` layout for multi-graph projects.
- [references/serving.md](references/serving.md) — AG-UI endpoint, Azure AI Foundry hosted agent,
  OpenAI-Responses-shape local testing endpoint, OpenTelemetry wiring.
