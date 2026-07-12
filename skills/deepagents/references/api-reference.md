# API Reference

Source pages fetched for this file: `overview.md`, `backends.md`, `subagents.md`, `customization.md`,
`tools.md`, `quickstart.md`, and the `models` provider-config doc (`/oss/python/langchain/models.md`).
Where the fetched summaries didn't include an exact signature, that's called out explicitly rather
than guessed.

## `create_deep_agent` parameters

Pulled from the Customization guide's parameter list. Treat this as a summary — verify against
`https://reference.langchain.com/python/deepagents/` for the authoritative, versioned signature
before relying on any parameter not shown elsewhere in this file with a working code sample.

| Parameter | Purpose |
|---|---|
| `model` | `"provider:model"` string or a LangChain chat model instance |
| `system_prompt` | Custom instructions for the main agent |
| `tools` | List of callables / LangChain tools / MCP tools |
| `memory` | `AGENTS.md`-style file paths loaded at startup (see SKILL.md §6) |
| `skills` | List of skill source directories (agentskills.io format) |
| `backend` | Filesystem backend instance (default: `StateBackend()`) |
| `subagents` | List of `SubAgent` dicts or `CompiledSubAgent` objects |
| `middleware` | Additional middleware instances |
| `interrupt_on` | Human-in-the-loop config, e.g. `{"edit_file": True}` |
| `response_format` | Structured output schema for the main agent |
| `permissions` | List of `FilesystemPermission` rules (allow/deny over read/write + glob paths) |
| `store` | A LangGraph `BaseStore` instance — required when using `StoreBackend` (passed separately from `backend=`) |

### Default middleware stack (main agent), in order

1. `TodoListMiddleware`
2. `SkillsMiddleware` (only when `skills=` is provided)
3. `FilesystemMiddleware`
4. `SubAgentMiddleware`
5. `SummarizationMiddleware`
6. `PatchToolCallsMiddleware`
7. `AsyncSubAgentMiddleware` (for async subagents)
8. User-provided `middleware=`
9. Profile-specific middleware
10. Prompt-caching layers
11. `MemoryMiddleware` (only when `memory=` is provided)
12. `HumanInTheLoopMiddleware` (only when `interrupt_on=` is configured)

Middleware you pass can override a default by matching its `.name` property instead of being
appended. `FilesystemMiddleware` and `SubAgentMiddleware` are "required scaffolding" — passing
them to `excluded_middleware` raises `ValueError`. To hide filesystem *tools* without removing the
middleware, use `excluded_tools` on a registered `HarnessProfile`, or (from `deepagents>=0.7.0a4`)
pass a `tools=[...]` allowlist directly to a `FilesystemMiddleware` instance via `middleware=`.

## Built-in filesystem tools

| Tool | Description |
|---|---|
| `ls` | List files in a directory with metadata (size, modified time) |
| `read_file` | Read file contents with line numbers; supports offset/limit; returns multimodal content blocks for supported non-text files |
| `write_file` | Create a new file, or overwrite an existing one |
| `edit_file` | Exact string replacement in files (with a global-replace mode) |
| `delete` | Delete a file, or a directory and its contents recursively (requires `deepagents>=0.7.a1`; recursive delete requires `>=0.7.a2`) |
| `glob` | Find files matching patterns (e.g. `**/*.py`) |
| `grep` | Search file contents (files-only, content-with-context, or counts modes) |
| `execute` | Run shell commands — only present when the backend is a sandbox backend or `LocalShellBackend` |

Backends that don't support `delete` automatically hide that tool from the model. `read_file`
must always remain in a `FilesystemMiddleware(tools=[...])` allowlist — omitting it raises
`ValueError` at agent-creation time.

### Supported multimodal file extensions (via `read_file`)

| Type | Extensions |
|---|---|
| Image | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.heic`, `.heif` |
| Video | `.mp4`, `.mpeg`, `.mov`, `.avi`, `.flv`, `.mpg`, `.webm`, `.wmv`, `.3gpp` |
| Audio | `.wav`, `.mp3`, `.aiff`, `.aac`, `.ogg`, `.flac` |
| File | `.pdf`, `.ppt`, `.pptx` |

## Backends

### `StateBackend` (default)

Stores files in LangGraph agent state; persists across turns via checkpoints; **not** shared
across threads. Backend methods called outside graph execution won't take effect until the graph
actually runs.

```python
from deepagents import create_deep_agent
from deepagents.backends import StateBackend

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=StateBackend(),
)
```

### `FilesystemBackend`

Reads/writes real files under a configurable `root_dir`. Requires `virtual_mode=True` for path
sandboxing. Agents can access real secrets on disk this way — combine with human-in-the-loop
middleware for sensitive operations, and consider wrapping it in a `CompositeBackend` to separate
internal agent data from project files.

### `StoreBackend`

Persists across threads via a LangGraph `BaseStore`. Requires a namespace factory for
multi-user/tenant isolation:

```python
namespace=lambda rt: (rt.server_info.user.identity,)   # per-user isolation
```

`Runtime` (`rt`) exposes:
- `rt.context` — user-supplied context
- `rt.server_info` — server metadata (assistant ID, user)
- `rt.execution_info` — execution identity (thread ID, run ID)

Automatically provisioned on LangSmith Deployment. Pass the actual store via `store=` on
`create_deep_agent`, separate from the `backend=` argument.

### `ContextHubBackend`

Mounts LangSmith Hub repos as a filesystem: the agent repo sits at root, skill repos appear under
`/skills/`. Supports lazy loading with in-memory caching and optimistic parent-commit writes
(retries on conflict). Gives durable storage without standing up a separate LangGraph store.

### `CompositeBackend`

Routes paths to different backends by prefix match; longer prefixes win. The canonical pattern
routes `/memories/` to a persistent `StoreBackend` while everything else stays ephemeral:

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
    store=InMemoryStore(),  # store passed to create_deep_agent, not to the backend
)
```

### `LocalShellBackend` — dev-only

> "This backend grants agents direct filesystem read/write access **and** unrestricted shell
> execution on your host. Use with extreme caution and only in appropriate environments."

Extends `FilesystemBackend` with an `execute` tool that runs directly on the host, no sandboxing.
Appropriate for local development CLIs, personal dev environments, or CI/CD with proper secret
management. **Not** appropriate for production web servers/APIs/multi-tenant systems, or for
processing untrusted input — an agent with this backend can run arbitrary shell commands with
your user's permissions and read any file it can access, including secrets, and changes are
irreversible.

```python
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    backend=LocalShellBackend(root_dir=".", virtual_mode=True, env={"PATH": "/usr/bin:/bin"}),
)
```

`LocalShellBackend` also supports `timeout`, `max_output_bytes`, and custom `env` variables per the
backends doc summary — verify exact kwarg names/defaults against
`https://reference.langchain.com/python/deepagents/` before depending on anything beyond
`root_dir`, `virtual_mode`, and `env`, which were confirmed in the fetched snippet above.

### Sandbox backends

Isolated environments implementing `SandboxBackendProtocolV2`; when detected, the harness adds the
`execute` tool automatically. Providers referenced in the docs: LangSmith-managed, Daytona (native
git operations), E2B, Modal, Runloop, Vercel, AgentCore, NVIDIA OpenShell. Each requires installing
its own `langchain-*` integration package and provider-specific auth. Example (Daytona):

```python
sandbox = Daytona().create()
backend = DaytonaSandbox(sandbox=sandbox)

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    system_prompt="You are a Python coding assistant with sandbox access.",
    backend=backend,
)
```

**Never put secrets inside a sandbox** — a context-injected agent can read and exfiltrate them.
Keep secrets in external tools, or use a network proxy that injects credentials without exposing
them to the model. See [patterns.md](patterns.md#sandbox-selection) for the two integration
patterns (agent-in-sandbox vs. sandbox-as-tool) and provider selection notes.

### Custom backend

Subclass `BackendProtocol` and implement:

- `ls(path)` → `LsResult`
- `read(file_path, offset, limit)` → `ReadResult`
- `write(file_path, content)` → `WriteResult`
- `edit(file_path, old_string, new_string, replace_all)` → `EditResult`
- `glob(pattern, path)` → `GlobResult`
- `grep(pattern, path, glob)` → `GrepResult`
- `delete(file_path)` → `DeleteResult` (optional)

For shell execution, implement `SandboxBackendProtocol`, which extends `BackendProtocol` with an
`execute` method.

### Filesystem permissions

Passed as `permissions=[...]` on `create_deep_agent`, evaluated top-to-bottom, first match wins.
Each rule:

- `operations`: `"read"` and/or `"write"`
- `paths`: glob patterns for files/directories
- `mode`: `"allow"` or `"deny"`

If no rule matches, the operation is allowed. Permissions govern the built-in filesystem tools
only — **not** sandbox `execute`, which supports arbitrary command execution and needs backend
policy hooks instead for custom validation (rate limiting, audit logging, content inspection).

## Model strings

`model=` is resolved through `init_chat_model`'s `"provider:model"` convention, or you can pass a
chat model instance directly.

| Provider | Example |
|---|---|
| Anthropic | `"anthropic:claude-sonnet-4-6"` |
| OpenAI | `"openai:gpt-5.5"` |
| Google Gemini | `"google_genai:gemini-3.5-flash"` |
| OpenRouter | `"openrouter:z-ai/glm-5.2"` |
| Fireworks | `"fireworks:accounts/fireworks/models/glm-5p2"` |
| Baseten | `"baseten:zai-org/GLM-5.2"` |
| Ollama | `"ollama:north-mini-code-1.0"` |

### Azure OpenAI

The `models` doc shows two verified forms:

```python
import os
from langchain.chat_models import init_chat_model

os.environ["AZURE_OPENAI_API_KEY"] = "..."
os.environ["AZURE_OPENAI_ENDPOINT"] = "..."

model = init_chat_model(
    "azure_openai:gpt-5.5",
    azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
)
```

```python
from langchain_openai import AzureChatOpenAI
import os

os.environ["AZURE_OPENAI_API_KEY"] = "..."
os.environ["AZURE_OPENAI_ENDPOINT"] = "..."

model = AzureChatOpenAI(
    model="gpt-5.5",
    azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
)
```

Pass the resulting `model` object to `create_deep_agent(model=model, ...)` — the fetched docs
don't show `azure_deployment` being accepted as a kwarg directly on `create_deep_agent`'s `model=`
string form, so build the model object first when you need the deployment name set explicitly.

### Gateway / OpenAI-compatible base URL (LiteLLM proxy, Together AI, vLLM, etc.)

```python
from langchain.chat_models import init_chat_model

model = init_chat_model(
    model="MODEL_NAME",
    model_provider="openai",
    base_url="BASE_URL",
    api_key="YOUR_API_KEY",
)
```

Explicit warning from the docs: `model_provider="openai"` (or direct `ChatOpenAI` usage) targets
the official OpenAI API spec — provider-specific fields from routers/proxies may not be extracted
or preserved. **For OpenRouter and LiteLLM specifically, the docs recommend the dedicated
integrations instead of generic `base_url`:**

- OpenRouter via `ChatOpenRouter` (`langchain-openrouter`)
- LiteLLM via `ChatLiteLLM` / `ChatLiteLLMRouter` (`langchain-litellm`)

HTTP proxy configuration (separate from a gateway base URL) varies by integration; one example
shown in the docs:

```python
from langchain_openai import ChatOpenAI

model = ChatOpenAI(
    model="gpt-5.5",
    openai_proxy="http://proxy.example.com:8080",
)
```

## Subagents

`subagents=` accepts a list of `SubAgent` dicts or `CompiledSubAgent` objects.

### `SubAgent` dict fields

| Field | Type | Notes |
|---|---|---|
| `name` | `str` | Required. Unique id; used by `task()`; becomes `AIMessage`/streaming metadata |
| `description` | `str` | Required. Drives the main agent's delegation decision |
| `system_prompt` | `str` | Required. Does **not** inherit from the main agent |
| `tools` | `list[Callable]` | Optional. Inherits main agent's tools by default; when specified, fully overrides them |
| `model` | `str \| BaseChatModel` | Optional. Overrides main agent's model; inherits by default |
| `middleware` | `list[Middleware]` | Optional. Does not inherit; merges into the default subagent middleware stack by `.name` matching |
| `interrupt_on` | `dict[str, bool \| InterruptOnConfig]` | Optional. Inherits from main agent by default |
| `skills` | `list[str]` | Optional. Does not inherit (only `general-purpose` inherits skills) |
| `response_format` | `ResponseFormat` | Optional. Requires `deepagents>=0.5.3`. Parent receives JSON instead of free text |
| `permissions` | `list[FilesystemPermission]` | Optional. **Replaces** parent's permissions entirely when set |

```python
research_subagent = {
    "name": "research-agent",
    "description": "Used to research more in depth questions",
    "system_prompt": "You are a great researcher",
    "tools": [internet_search],
    "model": "openai:gpt-5.5",
}

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    subagents=[research_subagent],
)
```

### `CompiledSubAgent`

Wraps a prebuilt LangGraph graph (must be `.compile()`d, or built via `langchain.agents.create_agent`)
that has a `"messages"` state key:

```python
from deepagents import CompiledSubAgent, create_deep_agent
from langchain.agents import create_agent

custom_graph = create_agent(
    model="openai:gpt-5.5",
    tools=[],
    system_prompt="You are a specialized agent for data analysis...",
)

custom_subagent = CompiledSubAgent(
    name="data-analyzer",
    description="Specialized agent for complex data analysis tasks",
    runnable=custom_graph,
)

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    subagents=[custom_subagent],
)
```

### Default `general-purpose` subagent

Added automatically unless you supply your own `subagents=[...]` entry named `"general-purpose"`.
It inherits the main agent's skills, has access to the same tools, and uses the same model unless
overridden. To disable it (and the `task` tool) entirely:

1. `general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False)` on the active harness
   profile.
2. Pass no synchronous `subagents=` on `create_deep_agent`.

Do not attempt to remove `SubAgentMiddleware` via `excluded_middleware` — it is required
scaffolding and raises `ValueError`. Async subagents are unaffected by disabling the sync default.

## MCP tools

```python
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from deepagents import create_deep_agent


async def main():
    client = MultiServerMCPClient(
        {
            "my_server": {
                "transport": "http",
                "url": "http://localhost:8000/mcp",
            }
        }
    )
    tools = await client.get_tools()

    agent = create_deep_agent(model="anthropic:claude-sonnet-4-6", tools=tools)

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Use the MCP server to help me."}]},
        config={"configurable": {"thread_id": "1"}},
    )


asyncio.run(main())
```

`langchain-mcp-adapters` also supports stdio servers, OAuth, and tool filtering per the tools doc
summary — the fetched content didn't include verbatim code for those variants, so verify against
`https://docs.langchain.com/oss/python/deepagents/tools` and the `langchain-mcp-adapters` package
docs before relying on exact parameter names for stdio/OAuth configs.

## PyPI package facts (verified via PyPI JSON API)

- Name: `deepagents`
- Version at time of writing: **0.6.12**
- `requires_python`: `>=3.11,<4.0`
- Core deps include `langchain-core>=1.4.8,<2.0.0`, `langchain>=1.3.11,<2.0.0`,
  `langchain-anthropic>=1.4.7,<2.0.0`, `langchain-google-genai>=4.2.5,<5.0.0`, `langsmith>=0.8.11`,
  `wcmatch>=10.1`.
- Optional extras: `aws` (`langchain-aws`), `quickjs` (`langchain-quickjs`, for the code
  interpreter / dynamic subagent dispatch).
