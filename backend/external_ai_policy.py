"""Fail-closed approval gate for outgoing Codex/ChatGPT requests.

This gate is not a DLP engine. It prevents accidental calls without an explicit
local administrator switch AND an approval for the individual request.
It cannot validate whether the user has organizational authorization.
"""
import os
from typing import Annotated

from fastapi import Header, HTTPException


def require_external_ai_approval(
    x_external_ai_approved: Annotated[str | None, Header(alias="X-External-AI-Approved")] = None,
) -> None:
    if os.getenv("AIC_EXTERNAL_AI_ENABLED") != "1":
        raise HTTPException(
            status_code=403,
            detail="Ekstern AI er slået fra. Administrator skal først godkende og aktivere AIC_EXTERNAL_AI_ENABLED=1.",
        )
    if x_external_ai_approved != "true":
        raise HTTPException(
            status_code=403,
            detail="Godkend datadeling for denne kørsel. Brug ikke fortroligt eller organisationsinternt materiale.",
        )
