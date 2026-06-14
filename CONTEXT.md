# Idea Council

A multi-agent council that evaluates a product idea end to end: a pipeline of
specialist agents each produce a report, and a synthesis agent renders a verdict.
This file fixes the project's domain language so modules, tests, and docs name
things the same way.

## Language

**Run**:
One end-to-end evaluation of a single idea — the pipeline executed once, with its
agent reports and final verdict.
_Avoid_: job, session, execution.

**Agent report**:
The markdown output of one council agent for a run, identified by the agent's name.
_Avoid_: result, output, response.

**Verdict**:
The synthesis agent's final GO / NO-GO / CONDITIONAL GO judgement for a run.
_Avoid_: decision, conclusion, recommendation.

**RunStore**:
The module that owns persistence of runs and their agent reports. The single seam
through which the orchestrator writes and the API reads; no caller touches the ORM
session or models directly.
_Avoid_: repository, DAO, persistence layer, RunRepository.

**RunView**:
The detached, read-only snapshot of a run (id, idea, status, verdict, reports) that
crosses the RunStore seam. Plain data — never a live ORM row.
_Avoid_: RunDTO, RunRecord, RunModel.

**RunStatus**:
The lifecycle state of a run: `pending`, `running`, `completed`, `failed`.
_Avoid_: state, phase, stage.

**CouncilModel**:
The seam a council agent calls to reach the language model:
`complete(prompt, *, tools)` returns text. All LangChain/Anthropic machinery lives
behind it — production is `AnthropicModel`; tests inject a fake. Agents are prompt
authors and never import LangChain.
_Avoid_: LLM client, ChatModel, provider, llm.
