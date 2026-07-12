# Serving a DeepAgents Agent

How to expose a `create_deep_agent` graph over HTTP beyond `langgraph dev`: the AG-UI protocol,
Azure AI Foundry hosted agents, and OpenTelemetry wiring. Everything in this file is verified
against a working, tested implementation (the `dvm-eaagent` project: `endpoints.py`,
`azure_foundry.py`, `telemetry.py`, `server.py`, `docs/foundry.md`) — deviations or untested
claims are flagged inline.

## Checkpointer prerequisite (applies to AG-UI and Foundry)

Both serving adapters below call LangGraph state APIs on the graph. Build the agent **with a
checkpointer** when self-hosting:

```python
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[...],
    system_prompt="...",
    checkpointer=InMemorySaver(),
    name="my-agent",
)
```

- `ag-ui-langgraph` calls `graph.aget_state()` internally, which raises
  `ValueError("No checkpointer set")` without one (verified locally in dvm-eaagent).
- The Azure Foundry adapter also requires it, and requires the graph state to be
  `MessagesState`-compatible (the adapter checks `is_state_schema_valid`; `create_deep_agent`
  graphs pass because they use a `messages` key).
- **Exception:** for `langgraph dev` / LangGraph platform deployments, build with **no**
  checkpointer — the platform injects its own persistence layer and an explicit one on the graph
  conflicts with it. The working pattern is a factory with a flag:

```python
def build_agent(*, checkpointer: bool = True):
    return create_deep_agent(
        ...,
        checkpointer=InMemorySaver() if checkpointer else None,
    )

def get_graph():
    """Module-level factory for langgraph.json — platform provides persistence."""
    return build_agent(checkpointer=False)
```

`InMemorySaver` is not durable across restarts — fine for a single-process server, swap for a
persistent checkpointer if you need durable threads.

## AG-UI protocol endpoint (`POST /agui`)

[AG-UI](https://docs.ag-ui.com) is an SSE-based protocol for agent frontends (CopilotKit speaks it
natively). The official integration is the **`ag-ui-langgraph`** PyPI package (module
`ag_ui_langgraph`), which ships `LangGraphAgent` and `add_langgraph_fastapi_endpoint`. The small
`ag-ui-protocol` package (module `ag_ui`) contains only the pydantic event models + SSE encoder —
no server.

```bash
pip install ag-ui-langgraph fastapi uvicorn   # ag-ui-langgraph>=0.0.42 verified
```

Simplest form (official helper):

```python
from ag_ui_langgraph import LangGraphAgent, add_langgraph_fastapi_endpoint
from fastapi import FastAPI

app = FastAPI()
agui_agent = LangGraphAgent(name="my-agent", graph=agent)   # agent = create_deep_agent(..., checkpointer=InMemorySaver())
add_langgraph_fastapi_endpoint(app, agui_agent, "/agui")
```

This mounts a POST route returning `text/event-stream` SSE with AG-UI's documented event types
(`RUN_STARTED`, `TEXT_MESSAGE_START/CONTENT/END`, `STATE_SNAPSHOT`, `STEP_STARTED/FINISHED`,
`RUN_FINISHED`, ...) — confirmed by an actual local smoke test in dvm-eaagent (stub graph +
`InMemorySaver`, POST to the route, real SSE `data:` lines read back).

### The RUN_ERROR-guarding wrapper (recommended over the raw helper)

The official endpoint has a real gap: **any mid-run exception (e.g. a failed LLM call) kills the
socket without a terminal event**, which AG-UI clients surface as an opaque transport error.
The verified fix is to mount the same shape yourself with a guarded generator, so clients get a
proper `RUN_ERROR` event and a clean stream end:

```python
from ag_ui.core import EventType, RunAgentInput
from ag_ui.encoder import EventEncoder
from ag_ui_langgraph import LangGraphAgent
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()
agui_agent = LangGraphAgent(name="my-agent", graph=agent)

# Same shape as ag_ui_langgraph.add_langgraph_fastapi_endpoint, but with the
# event generator guarded so mid-run exceptions reach the client as RUN_ERROR.
@app.post("/agui")
async def agui_endpoint(input_data: RunAgentInput, request: Request):
    from ag_ui.core.events import RunErrorEvent

    encoder = EventEncoder(accept=request.headers.get("accept"))
    request_agent = agui_agent.clone()

    async def event_generator():
        try:
            async for event in request_agent.run(input_data):
                yield encoder.encode(event)
        except Exception as exc:  # must reach the client as RUN_ERROR
            yield encoder.encode(
                RunErrorEvent(type=EventType.RUN_ERROR, message=f"{type(exc).__name__}: {exc}")
            )

    return StreamingResponse(event_generator(), media_type=encoder.get_content_type())
```

### Pitfall: `from __future__ import annotations` + FastAPI forward refs

If your endpoints module uses `from __future__ import annotations`, every type hint — including
ones on functions defined *inside* another function — becomes a string forward reference.
FastAPI/Pydantic resolve those against the **module's global namespace** when building the
request-body model. A type imported only inside a function (e.g. a local
`from ag_ui.core import RunAgentInput`) is invisible to that resolution and fails in a confusing
way: FastAPI silently treats the unresolvable-typed parameter as a *query* param instead of a body
param, and the OpenAPI schema build later raises
`PydanticUserError: ... is not fully defined`. Verified by reproducing exactly this failure in
dvm-eaagent. **Fix: import request-body types (`RunAgentInput` etc.) at module scope.**

### Testing the endpoint

Raw SSE with curl (`RunAgentInput` uses camelCase field aliases on the wire):

```bash
curl -N -X POST http://localhost:8000/agui -H 'content-type: application/json' -d '{
  "threadId": "t1", "runId": "r1", "state": {},
  "messages": [{"id": "m1", "role": "user", "content": "hello"}],
  "tools": [], "context": [], "forwardedProps": {}
}'
```

Or the official TypeScript client (`@ag-ui/client`, the same library the AG-UI dojo is built on —
verified against this endpoint shape):

```js
// npm install @ag-ui/client ; node test.mjs
import { HttpAgent } from "@ag-ui/client";
const agent = new HttpAgent({ url: "http://localhost:8000/agui", threadId: "t1" });
agent.messages = [{ id: "m1", role: "user", content: "hello" }];
const result = await agent.runAgent({ runId: "r1" });
console.log(result.newMessages);
```

For a full chat UI, point any CopilotKit frontend at the endpoint via `HttpAgent`. Note there is
no config-only way to point the hosted AG-UI dojo at an arbitrary URL — running the dojo against a
custom endpoint requires registering an integration inside the dojo monorepo
(`apps/dojo/src/agents.ts` + `menu.ts`).

## Azure AI Foundry hosted agent

Foundry hosted agents run your container image on Microsoft-managed compute behind a fixed runtime
contract. The official adapter is **`azure-ai-agentserver-langgraph`** (+ its core dependency
`azure-ai-agentserver-core`).

### Pin matching prerelease versions — version skew breaks imports

Both packages are prerelease-only on PyPI and their version numbers drift independently (core has
published `2.0.0bN` while the langgraph adapter is still on `1.0.0bN`). Installing them unpinned
resolves each to its own latest and **breaks at import time** with
`ModuleNotFoundError: No module named 'azure.ai.agentserver.core.client'` — verified by
reproducing the failure. Pin both to the same matching prerelease:

```toml
# pyproject.toml
[project.optional-dependencies]
foundry = [
    "azure-ai-agentserver-langgraph==1.0.0b17",
    "azure-ai-agentserver-core==1.0.0b17",
]
```

(1.0.0b17 was the verified matching pair at time of writing; newer matching pairs may exist —
the invariant is *matching* versions, not that exact number.)

### Adapter usage

```python
import os
from azure.ai.agentserver.langgraph import from_langgraph

graph = build_agent()          # create_deep_agent(..., checkpointer=InMemorySaver())
adapter = from_langgraph(graph)

port = int(os.environ.get("DEFAULT_AD_PORT", 8088))
adapter.run(port=port)         # blocking; Microsoft's own Starlette server, not your FastAPI app
```

Verified facts (read directly from the installed package source,
`azure/ai/agentserver/core/server/base.py`, and exercised locally):

- `from_langgraph(compiled_graph)` returns a `LangGraphAdapter` (a `FoundryCBAgent` subclass);
  its `.app` is a **Starlette** application exposing exactly:
  - `POST /runs` — Foundry's native invocation contract
  - `POST /responses` — OpenAI Responses API-compatible contract
  - `GET /liveness`, `GET /readiness` — probes
- Default port **8088**, overridable via the `DEFAULT_AD_PORT` env var (the literal signature is
  `def run(self, port: int = int(os.environ.get("DEFAULT_AD_PORT", 8088)))`).
- `FoundryCBAgent.run()` calls `self.init_tracing()` before serving — it reads the OTLP endpoint
  env var and an Application Insights connection string itself, so OTel needs no extra code in
  this mode.
- **`AZURE_AI_PROJECT_ENDPOINT` is effectively required**: the adapter's tool-call path
  unconditionally resolves Foundry tools via `AgentServerContext`/`FoundryToolRuntime` and raises
  `RuntimeError("FoundryToolRuntime is not configured...")` on **every** `/responses` or `/runs`
  call unless `AZURE_AI_PROJECT_ENDPOINT` plus Azure credentials are present (verified by
  reproducing the error with a stub graph and no Azure project). Expected in a real deployment
  (the platform injects a project endpoint); it means the adapter **cannot fully answer requests
  in a bare local dev environment**.
- When serving through the adapter, none of your own FastAPI routes exist — only the four routes
  above.
- Container images for Foundry must be **linux/amd64** (`docker build --platform linux/amd64` on
  Apple Silicon). Don't bake secrets into the image/env in production — use managed identity /
  Key Vault, per Microsoft's guidance.

Typical real-deployment env:

```bash
export AZURE_AI_PROJECT_ENDPOINT=https://<project>.services.ai.azure.com/api/projects/<project>
export AZURE_OPENAI_API_KEY=...        # or managed identity
export AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
```

Still **unverified against a real Foundry deployment** (flagged as assumed in the source repo's
docs too): which probe path the platform actually calls, the per-session `$HOME`/`/files`
persistence and idle-deprovision cycle, sandbox sizing/billing tiers, and whether
`AZURE_AI_PROJECT_ENDPOINT` is auto-injected at deploy time or must be set in the deployment's
env vars.

### Local-testing alternative: hand-rolled OpenAI-Responses-shape endpoint

Because the real adapter can't answer requests without Azure credentials, the verified pattern for
local testing is a minimal FastAPI route implementing just the Responses API request/response
*shape* (`input` string-or-messages in, a `response` object with `output` items out) against the
agent directly:

```python
import time, uuid
from typing import Any

from fastapi import APIRouter
from langchain_core.messages import AIMessage
from pydantic import BaseModel


class ResponsesRequest(BaseModel):
    model: str | None = None
    input: str | list[dict[str, Any]]
    previous_response_id: str | None = None
    thread_id: str | None = None
    stream: bool = False


def build_responses_router(get_agent) -> APIRouter:
    router = APIRouter()

    @router.post("/responses")
    def create_response(req: ResponsesRequest):
        agent = get_agent()
        thread_id = req.previous_response_id or req.thread_id or str(uuid.uuid4())
        text = req.input if isinstance(req.input, str) else "\n".join(
            str(m.get("content", "")) for m in req.input
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": text}]},
            config={"configurable": {"thread_id": thread_id}},
        )
        reply = next(
            (m.content for m in reversed(result.get("messages", []))
             if isinstance(m, AIMessage) and m.content),
            "",
        )
        return {
            "id": f"resp_{uuid.uuid4().hex}",
            "object": "response",
            "created_at": int(time.time()),
            "status": "completed",
            "model": req.model or "my-agent",
            "thread_id": thread_id,   # extension: pass back to continue the thread
            "output": [{
                "id": f"msg_{uuid.uuid4().hex}",
                "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": reply, "annotations": []}],
            }],
            "output_text": reply,
        }

    return router
```

This deliberately implements only a subset (no tool-calling passthrough, no real
`previous_response_id` chaining beyond thread reuse, no file/image parts) — it lets
Responses-API-shaped clients be tested locally with only model credentials, and is **not** a
substitute for the actual hosted-agent contract (no `/runs`, no probes, different default port).

## OpenTelemetry

The verified pattern: **no-op by default, opt-in purely via standard `OTEL_*` env vars**, so the
same build runs traced or untraced with zero config changes. Split dependencies so the always-on
part is only `opentelemetry-api` (whose built-in tracer is a no-op), and put the SDK + exporters +
instrumentations behind an optional extra:

```toml
[project]
dependencies = ["opentelemetry-api>=1.43"]

[project.optional-dependencies]
otel = [
    "opentelemetry-sdk>=1.43",
    "opentelemetry-exporter-otlp>=1.43",
    "opentelemetry-instrumentation-fastapi>=0.64b0",
    "opentelemetry-instrumentation-langchain>=0.53.3",
]
```

Env vars honored (standard OTel names — <https://opentelemetry.io/docs/languages/sdk-configuration/>):

| Var | Meaning |
|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP collector, e.g. `http://localhost:4318` — presence enables tracing |
| `OTEL_TRACES_EXPORTER` | `otlp` (default) \| `console` \| `none` — presence also enables tracing (bare `console` with no endpoint is a common local pattern) |
| `OTEL_SERVICE_NAME` | overrides the default `service.name` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc` (default) \| `http/protobuf` |
| `OTEL_SDK_DISABLED` | `true` forces a hard no-op regardless of the above |

Setup skeleton (condensed from the verified `telemetry.py`; make it idempotent — it may be called
from both a CLI entry point and the server module):

```python
import os
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def setup_telemetry(app=None) -> bool:
    if os.environ.get("OTEL_SDK_DISABLED", "").lower() == "true":
        return False
    if not (os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") or os.environ.get("OTEL_TRACES_EXPORTER")):
        return False  # no-op: opentelemetry-api's built-in no-op tracer stays in place

    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", "my-agent")})
    )
    exporter_kind = os.environ.get("OTEL_TRACES_EXPORTER", "otlp").lower()
    if exporter_kind == "console":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif exporter_kind != "none":
        if os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc").lower() == "http/protobuf":
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        else:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    # LLM/chain spans — see instrumentation choice below
    from opentelemetry.instrumentation.langchain import LangchainInstrumentor
    LangchainInstrumentor().instrument()

    # HTTP spans
    if app is not None:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    return True
```

In the real implementation every `import`/`instrument()` call is wrapped in try/except with a
logged warning — **instrumentation must never break app startup**; copy that discipline.

**LangChain instrumentation choice (verified 2026-07 against langchain 1.3.x / langgraph 1.2.x):**
`opentelemetry-instrumentation-langchain` (the openllmetry project's package, 0.53.x) imports and
instruments cleanly and is the best-supported OTel integration found for langchain 1.x. There is
no native OTel support built into langchain/langgraph itself, and LangSmith's OTEL export is
LangSmith-account-specific rather than a generic OTLP sink, so it isn't a substitute for a plain
collector.

Call `setup_telemetry(app)` from a FastAPI lifespan hook (after routes exist), and note that in
`--foundry` mode the Azure adapter does its own `init_tracing()` — don't double-instrument there.

Run traced locally:

```bash
# macOS / Linux
OTEL_TRACES_EXPORTER=console uvicorn myapp.server:app
# or against a collector:
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf uvicorn myapp.server:app
```

```powershell
# Windows (PowerShell)
$env:OTEL_TRACES_EXPORTER = "console"; uvicorn myapp.server:app
```

## Token usage reporting

Verified pattern (from the working `usage.py` / `server.py` `/chat` handler / `cli.py` REPL in
dvm-eaagent) for reporting per-turn token usage from any serving surface.

### Where usage lives

Every `AIMessage` carries `usage_metadata`, populated by the provider integration (e.g.
`langchain-anthropic`): `input_tokens`, `output_tokens`, `total_tokens`, plus
`input_token_details` (`cache_read`, `cache_creation`) and `output_token_details` (`reasoning` —
Anthropic "thinking" tokens when extended thinking is enabled).

### A turn is several model calls — aggregate over the turn's new AIMessages

A single agent turn usually contains multiple model calls (tool-use loops), each producing its own
`AIMessage` with its own `usage_metadata`. Per-turn usage is therefore the **sum over the
AIMessages produced in that turn**:

```python
from typing import Any
from langchain_core.messages import AIMessage


def aggregate_usage(messages: list[Any], since_ids: set[str] | None = None) -> dict[str, int]:
    """Sum usage_metadata over the AIMessages in `messages`.

    Pass `since_ids` = the message ids present BEFORE the turn to get per-turn
    usage from a thread that carries history.
    """
    totals = {
        "input_tokens": 0, "cached_input_tokens": 0, "thinking_tokens": 0,
        "output_tokens": 0, "total_tokens": 0, "model_calls": 0,
    }
    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        if since_ids is not None and msg.id in since_ids:
            continue
        usage = getattr(msg, "usage_metadata", None)
        if not usage:
            continue
        in_details = usage.get("input_token_details") or {}
        out_details = usage.get("output_token_details") or {}
        totals["input_tokens"] += usage.get("input_tokens", 0) or 0
        totals["cached_input_tokens"] += in_details.get("cache_read", 0) or 0
        totals["thinking_tokens"] += out_details.get("reasoning", 0) or 0
        totals["output_tokens"] += usage.get("output_tokens", 0) or 0
        totals["total_tokens"] += usage.get("total_tokens", 0) or 0
        totals["model_calls"] += 1
    return totals
```

### The prior-message-ids snapshot (threads with history)

`agent.invoke(...)` returns the **full thread state**, not just the new turn, when the graph has a
checkpointer and the thread has history. To isolate the turn, snapshot the message ids from
`agent.get_state(config)` **before** invoking, then skip those ids when aggregating — the verified
`/chat` handler pattern:

```python
config = {"configurable": {"thread_id": thread_id}}

# Snapshot message ids before the turn so usage is per-turn, not per-thread.
prior_ids: set[str] = set()
state = agent.get_state(config)
if state and state.values:
    prior_ids = {m.id for m in state.values.get("messages", []) if getattr(m, "id", None)}

result = agent.invoke({"messages": [{"role": "user", "content": text}]}, config=config)
usage = aggregate_usage(result.get("messages", []), prior_ids)
# e.g. include it in the HTTP response: {"reply": ..., "thread_id": ..., "usage": usage}
```

The same pattern works in a streaming CLI REPL: snapshot `prior_ids`, stream with
`stream_mode="values"` keeping the last chunk's `messages`, then print
`aggregate_usage(final_messages, prior_ids)` as a one-liner after each turn (e.g.
`tokens: in=... (cached=...) thinking=... out=... calls=...`).

### Prompt caching is already on for Anthropic — cache_read just works

`create_deep_agent` auto-appends `AnthropicPromptCachingMiddleware` (ephemeral cache, 5-minute
TTL; a no-op for non-Anthropic models) to the middleware stack, so `cache_read` is populated for
Anthropic models with **no setup at all**. Real measured example from the working implementation:
turn 2 of a thread reported `input=11705` with `cached=11689` — nearly the whole repeated prefix
(system prompt, skills, memory, tool schemas) served from cache.

### Caveat: usage over AG-UI

Whether these usage numbers reach an AG-UI frontend depends on what the `ag-ui-langgraph` adapter
forwards in its state/messages events — **unverified**; the verified implementations report usage
via their own `/chat` JSON response and the CLI REPL instead. Inspect the adapter's emitted
`STATE_SNAPSHOT`/message events (or add usage to your own endpoint's response) before relying on
AG-UI delivery.
