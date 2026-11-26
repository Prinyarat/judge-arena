from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Column, JSON

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    is_admin: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Problem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    title: str
    statement: str
    difficulty: str = "Easy"
    time_limit_ms: int = 2000
    memory_limit_mb: int = 256
    tests: list = Field(default_factory=list, sa_column=Column(JSON))
    visible: bool = True

class Contest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str = ""
    start_at: datetime
    end_at: datetime
    problem_ids: list = Field(default_factory=list, sa_column=Column(JSON))

class Submission(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)
    problem_id: int = Field(index=True)
    contest_id: Optional[int] = Field(default=None, index=True)
    language: str
    source_code: str
    verdict: str = "QUEUED"
    score: int = 0
    time_ms: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
