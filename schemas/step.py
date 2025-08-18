from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


Intent = Literal[
    "profile",
    "clean",
    "encode",
    "select_features",
    "train",
    "tune",
    "evaluate",
    "export",
]


class Step(BaseModel):
    intent: Intent
    needs: List[str] = Field(default_factory=list)
    provides: List[str] = Field(default_factory=list)
    python: str
    notes: Optional[str] = None


