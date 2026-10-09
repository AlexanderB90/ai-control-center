from typing import Annotated
import sqlite3

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints
from fastapi.middleware.cors import CORSMiddleware
from backend.agents.research_agent import AgentError, research_agent
from backend import history

app = FastAPI(
    title="AI Control Center API",
    version="0.3.0"
)

# Tillad vores lokale Next.js-frontend at kommunikere med API'et
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "AI Control Center",
        "version": "0.3.0"
    }


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=10000)]


@app.post("/agents/research/run")
def run_research_agent(request: ResearchRequest):
    try:
        result = research_agent.run(request.task)
    except AgentError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None
    try:
        history.save(request.task, result['response'], research_agent.name, research_agent.version)
    except (sqlite3.Error, OSError):
        return {**result, 'history_warning': history.SAVE_WARNING}
    return result


@app.get('/agents/research/history')
def research_history():
    try:
        return history.recent()
    except (sqlite3.Error, OSError):
        raise HTTPException(status_code=503, detail=history.ERROR_MESSAGE) from None


@app.get('/agents/research/history/{identifier}')
def research_history_detail(identifier: str):
    try:
        record = history.detail(identifier)
    except (sqlite3.Error, OSError):
        raise HTTPException(status_code=503, detail=history.ERROR_MESSAGE) from None
    if record is None:
        raise HTTPException(status_code=404, detail='Opgaven blev ikke fundet i historikken.')
    return record
