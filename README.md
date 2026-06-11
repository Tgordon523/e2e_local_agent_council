# Idea Council

A multi-agent council that evaluates a product idea end to end. You hand it an
idea in one sentence; six specialist agents review it in sequence — each one
building on the reports before it — and a final analyst renders a GO / NO-GO /
CONDITIONAL GO verdict. Every run and report is persisted through a `RunStore`
that writes to Postgres in production and in-memory SQLite in tests.

## The council

Agents run as a pipeline, in this order. Each agent sees the reports of every
agent that ran before it.

| Agent           | Role                                                | Web search | Requires priors            |
| --------------- | --------------------------------------------------- | :--------: | -------------------------- |
| `market`        | Market size, growth, competitors, risks             |     ✅     | —                          |
| `product`       | Existing products / availability landscape          |     ✅     | market                     |
| `art_direction` | Design direction and UX opportunity                 |     ✅     | product                    |
| `developer`     | Technical implementation plan and complexity        |     —      | market, product, art_direction |
| `qa`            | Testability and risk review                         |     —      | developer                  |
| `synthesis`     | Final verdict synthesizing all five reports         |     —      | market, product, art_direction, developer, qa |

## Architecture

### Module map

```
council/
├── domain.py          # Shared data types: AgentReport
├── run_store.py       # Persistence seam — RunStore, RunView, RunStatus
├── orchestrator.py    # Pipeline execution — run_council(), DEFAULT_PIPELINE
├── api.py             # FastAPI HTTP interface
├── run.py             # CLI entry point
├── db.py              # SQLAlchemy engine (Postgres)
├── models.py          # ORM models (dialect-portable: Postgres + SQLite)
└── agents/
    ├── base.py        # BaseCouncilAgent — LLM invocation, tool calling
    ├── _tools.py      # Search tool factory (Tavily → DuckDuckGo fallback)
    ├── market.py
    ├── product.py
    ├── art_direction.py
    ├── developer.py
    ├── qa.py
    └── synthesis.py
```

### Data flow

```
idea (str)
    │
    ▼
run_council(idea, store, pipeline)
    │
    ├─▶ store.create_run(idea)          # → run_id, status = running
    │
    ├─▶ [for each AgentClass in pipeline]
    │       agent = AgentClass()
    │       check agent.required_priors  # warn if any are missing
    │       report = agent.run(idea, prior_reports)   # → AgentReport
    │       store.record_report(run_id, report)       # committed immediately
    │
    └─▶ store.complete(run_id, verdict)  # status = completed

verdict (str)  ←  synthesis agent's report_text
```

### Key seams

**`RunStore`** is the persistence seam. The orchestrator writes through it
(`create_run`, `record_report`, `complete`, `fail`); the API reads through it
(`get`, `list_recent`). No caller ever sees an ORM session or model row —
writes take an `AgentReport`, reads return a detached `RunView`. Each write is
its own transaction, so reports survive a mid-pipeline crash.

The store accepts a SQLAlchemy engine at construction — Postgres in production,
in-memory SQLite in tests. The ORM models use dialect-portable column types so
the same schema runs on both without a parallel test schema.

**The pipeline** is data, not code. `run_council` accepts an optional `pipeline`
argument (a list of `BaseCouncilAgent` subclasses). The default is
`DEFAULT_PIPELINE` (all six agents in order), but any subset or ordering can be
passed — useful for quick evaluations or testing:

```python
from council.orchestrator import run_council
from council.agents.market import MarketAgent
from council.agents.synthesis import SynthesisAgent

# Quick two-agent run
run_id, verdict = run_council("My idea", pipeline=[MarketAgent, SynthesisAgent])
```

### Domain types (`council/domain.py`)

`AgentReport` is the shared data type that crosses both the agent layer and the
persistence seam. It lives in `council.domain` so neither layer needs to import
the other.

```python
@dataclass
class AgentReport:
    agent_name: str
    report_text: str
    metadata: dict
```

`RunView` and `RunStatus` live in `council.run_store` — they are the read-side
of the persistence seam and never leave it.

### Agent prior dependencies

Each concrete agent declares `required_priors` — the agent names whose reports
it needs to produce a high-quality output. The orchestrator checks this before
invoking each agent and logs a warning if any are missing. Agents still run when
priors are absent (all prior lookups are guarded), so custom pipelines work
without error.

## Stack

- **Python 3.12** (3.11+ supported)
- **LangChain + Anthropic Claude** (`claude-sonnet-4-6`) for the agents
- **Tavily** for web search, falling back to **DuckDuckGo** when no Tavily key is set
- **Postgres** via SQLAlchemy for persistence; SQLite (in-memory) for tests
- **FastAPI / uvicorn** for the optional HTTP API
- **Docker Compose** for a one-command local stack

## Prerequisites

- An [Anthropic API key](https://console.anthropic.com/) (required)
- A [Tavily API key](https://tavily.com/) (optional — better search; without it
  the search agents use DuckDuckGo, no key needed)
- Either **Docker + Docker Compose**, or **Python 3.11+ and a Postgres instance**

## Install & setup

### 1. Clone and configure

```bash
git clone <repo-url>
cd e2e_local_agent_council

cp .env.example .env
```

Edit `.env` and set your keys:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...     # required
TAVILY_API_KEY=tvly-...          # optional; omit to use DuckDuckGo
DATABASE_URL=postgresql://council:council@localhost:5432/council
```

### 2a. Run with Docker (recommended)

Docker Compose provisions Postgres and applies the schema (`alembic/init.sql`)
automatically on first start.

```bash
# Start (and initialize) the database
docker-compose up -d db
```

That's the whole setup — jump to **Usage → Docker** below to run an evaluation.

### 2b. Run locally (without Docker)

Install the package and its dependencies (a virtualenv is recommended):

```bash
pip install -e .            # add ".[dev]" to include the test tooling
```

Point at a running Postgres and apply the schema once:

```bash
# DATABASE_URL in your .env must match this database
psql "$DATABASE_URL" -f alembic/init.sql
```

> The app does not auto-create tables — apply `alembic/init.sql` before the
> first run (Docker does this for you).

## Usage

### CLI

```bash
python -m council.run "A subscription service for personalized dog food"
```

Per-agent progress is logged as it runs, and the final verdict is printed at the
end. A full run calls Claude for all six agents and typically takes a few
minutes.

### Docker

The `council` service runs the CLI inside the stack. The idea is passed via the
`IDEA` environment variable:

```bash
docker-compose run --rm -e IDEA="A subscription service for personalized dog food" council
```

(The DB must be up — see step 2a. `--rm` cleans up the one-off container.)

### HTTP API

Start the server (against the same database):

```bash
uvicorn council.api:app --reload
```

| Method & path      | Description                                              |
| ------------------ | ------------------------------------------------------- |
| `POST /evaluate`   | `{"idea": "..."}` — runs all six agents, returns the run |
| `GET /runs`        | List recent runs (`?limit=` 1–100, default 20)          |
| `GET /runs/{id}`   | Fetch a single run and its agent reports                |

`POST /evaluate` blocks until every agent finishes (a few minutes). Example:

```bash
curl -X POST http://localhost:8000/evaluate \
  -H "Content-Type: application/json" \
  -d '{"idea": "A subscription service for personalized dog food"}'
```

Interactive docs are available at `http://localhost:8000/docs`.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

No API key or real database is required:

- **LLM calls** are stubbed — agents never hit the Anthropic API.
- **Persistence** tests run the real `RunStore` and ORM models against
  in-memory SQLite, using dialect-portable column types so no Postgres
  schema is needed.
- **Orchestrator** tests pass mock agent classes directly via the `pipeline`
  parameter — no module-level patching.

## License

BSD 3-Clause — see [LICENSE](LICENSE).
