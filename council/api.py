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

from council.db import get_session
from council.models import AgentResult, Run
from council.orchestrator import run_council

app = FastAPI(title="Idea Council API", version="0.1.0")


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


def _run_to_out(run: Run, results=()) -> RunOut:
    """Map a Run ORM row (and its agent results) to the API response model."""
    return RunOut(
        id=run.id,
        idea_text=run.idea_text,
        created_at=run.created_at,
        status=run.status,
        final_verdict=run.final_verdict,
        agent_results=[
            AgentResultOut(
                agent_name=r.agent_name,
                report_text=r.report_text,
                created_at=r.created_at,
            )
            for r in results
        ],
    )


@app.post("/evaluate", response_model=RunOut)
def evaluate_idea(request: IdeaRequest):
    """Submit an idea. Blocks until all six agents complete (~2-5 min)."""
    run_id, _verdict = run_council(request.idea)

    with get_session() as session:
        run = session.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=500, detail="Run not found after completion")
        results = session.query(AgentResult).filter(AgentResult.run_id == run.id).all()
        return _run_to_out(run, results)


@app.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: uuid.UUID):
    with get_session() as session:
        run = session.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        results = session.query(AgentResult).filter(AgentResult.run_id == run_id).all()
        return _run_to_out(run, results)


@app.get("/runs", response_model=list[RunOut])
def list_runs(limit: int = Query(20, ge=1, le=100)):
    with get_session() as session:
        runs = session.query(Run).order_by(Run.created_at.desc()).limit(limit).all()
        return [_run_to_out(run) for run in runs]
