"""Options calculations, assessments and agent-scoped history."""
import json
import sqlite3
from fastapi import APIRouter, HTTPException
from backend import history
from backend.options import OptionsRequest, calculate
from backend.agents.options_agent import options_agent
from backend.agents.research_agent import AgentError

router = APIRouter(prefix="/agents/options")


@router.post("/calculate")
def calculate_options(request: OptionsRequest):
    return {"calculation": calculate(request)}


@router.post("/run")
def assess_options(request: OptionsRequest):
    calculation = calculate(request)
    result = {"agent": options_agent.name, "version": options_agent.version,
              "status": "success", "calculation": calculation, "response": "",
              "ai_warning": None}
    try:
        result["response"] = options_agent.run(json.dumps(calculation, ensure_ascii=False))["response"]
    except AgentError as error:
        result["status"] = "calculation_only"
        result["ai_warning"] = str(error)
    title = f"{request.symbol.upper()} · {request.strategy} · strike {request.strike} · {request.expiry}"
    try:
        history.save(title, json.dumps(result, ensure_ascii=False), options_agent.name, options_agent.version)
    except (sqlite3.Error, OSError):
        result["history_warning"] = history.SAVE_WARNING
    return result


@router.get("/history")
def options_history():
    try:
        return history.recent(options_agent.name)
    except (sqlite3.Error, OSError):
        raise HTTPException(status_code=503, detail=history.ERROR_MESSAGE) from None


@router.get("/history/{identifier}")
def options_history_detail(identifier: str):
    try:
        record = history.detail(identifier, options_agent.name)
        if record is not None:
            record["result"] = json.loads(record["response"])
    except (sqlite3.Error, OSError, ValueError):
        raise HTTPException(status_code=503, detail=history.ERROR_MESSAGE) from None
    if record is None:
        raise HTTPException(status_code=404, detail="Optionsopgaven blev ikke fundet.")
    return record
