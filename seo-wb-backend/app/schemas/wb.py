from typing import Any

from pydantic import BaseModel


class WBSubject(BaseModel):
    subjectID: int
    parentID: int | None = None
    subjectName: str
    parentName: str | None = None


class WBCharacteristic(BaseModel):
    charcID: int | None = None
    subjectName: str | None = None
    subjectID: int | None = None
    name: str
    required: bool = False
    unitName: str | None = None
    maxCount: int | None = None
    popular: bool = False
    charcType: int | None = None
    isVariable: bool = False
    raw: dict[str, Any] | None = None
