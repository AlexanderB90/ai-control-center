from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints
from fastapi.middleware.cors import CORSMiddleware
from backend.agents.research_agent import AgentError, research_agent

app = FastAPI(
    title="AI Control Center API",
    version="0.2.0"
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
        "version": "0.2.0"
    }


class ResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=10000)]


@app.post("/agents/research/run")
def run_research_agent(request: ResearchRequest):
    try:
        return research_agent.run(request.task)
    except AgentError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None
