"""
FastAPI server — optional interface alongside the CLI.

Start: uvicorn council.api:app --reload
POST  /evaluate     {"idea": "..."}  → runs all agents synchronously
GET   /runs/{id}    → fetch a completed run and its agent results
GET   /runs         → list recent runs
"""
import uuid
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from council.orchestrator import run_council
from council.run_store import RunView, default_run_store

app = FastAPI(title="Idea Council API", version="0.1.0")
store = default_run_store()


class IdeaRequest(BaseModel):
    idea: str = Field(..., min_length=1)


class AgentResultOut(BaseModel):
    agent_name: str
    report_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RunOut(BaseModel):
    id: uuid.UUID
    idea_text: str
    created_at: datetime
    status: str
    final_verdict: str | None
    agent_results: list[AgentResultOut] = []

    model_config = {"from_attributes": True}


def _view_to_out(view: RunView) -> RunOut:
    """Map a detached RunView to the API response model."""
    return RunOut(
        id=view.id,
        idea_text=view.idea_text,
        created_at=view.created_at,
        status=view.status.value,
        final_verdict=view.final_verdict,
        agent_results=[
            AgentResultOut(
                agent_name=r.agent_name,
                report_text=r.report_text,
                created_at=r.created_at,
            )
            for r in view.reports
        ],
    )


@app.post("/evaluate", response_model=RunOut)
def evaluate_idea(request: IdeaRequest):
    """Submit an idea. Blocks until all six agents complete (~2-5 min)."""
    run_id, _verdict = run_council(request.idea)

    view = store.get(run_id)
    if not view:
        raise HTTPException(status_code=500, detail="Run not found after completion")
    return _view_to_out(view)


@app.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: uuid.UUID):
    view = store.get(str(run_id))
    if not view:
        raise HTTPException(status_code=404, detail="Run not found")
    return _view_to_out(view)


@app.get("/runs", response_model=list[RunOut])
def list_runs(limit: int = Query(20, ge=1, le=100)):
    return [_view_to_out(view) for view in store.list_recent(limit)]
