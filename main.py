import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field as PField
from sqlmodel import Session, select
from .database import create_db, get_session
from .models import User, Problem, Contest, Submission
from .security import hash_password, verify_password, make_token, current_user, admin_user
from .judge import run_submission
from .seed import seed

app = FastAPI(title="Judge Arena API", version="1.1.0", docs_url="/docs")
STATIC = Path(__file__).resolve().parent.parent / "static"

class RegisterIn(BaseModel):
    username: str = PField(min_length=3, max_length=24, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = PField(min_length=8, max_length=72)

class LoginIn(BaseModel):
    username: str
    password: str

class ProblemIn(BaseModel):
    slug: str
    title: str
    statement: str
    difficulty: str = "Easy"
    time_limit_ms: int = 2000
    memory_limit_mb: int = 256
    tests: list[dict]
    visible: bool = True

class ContestIn(BaseModel):
    title: str
    description: str = ""
    start_at: datetime
    end_at: datetime
    problem_ids: list[int]

class SubmitIn(BaseModel):
    problem_id: int
    language: str
    source_code: str = PField(min_length=1, max_length=50000)
    contest_id: int | None = None

@app.on_event("startup")
def startup():
    create_db()
    with next(get_session()) as session:
        seed(session)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")

app.mount("/static", StaticFiles(directory=STATIC), name="static")

@app.post("/api/register")
def register(data: RegisterIn, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.username == data.username)).first():
        raise HTTPException(409, "Username already exists")
    user = User(username=data.username, password_hash=hash_password(data.password))
    session.add(user); session.commit(); session.refresh(user)
    return {"token": make_token(user), "username": user.username, "is_admin": user.is_admin}

@app.post("/api/login")
def login(data: LoginIn, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == data.username)).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Incorrect username or password")
    return {"token": make_token(user), "username": user.username, "is_admin": user.is_admin}

@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "username": user.username, "is_admin": user.is_admin}

@app.get("/api/problems")
def problems(session: Session = Depends(get_session)):
    rows = session.exec(select(Problem).where(Problem.visible == True)).all()
    return [{"id":p.id,"slug":p.slug,"title":p.title,"difficulty":p.difficulty} for p in rows]

@app.get("/api/problems/{problem_id}")
def problem_detail(problem_id: int, session: Session = Depends(get_session)):
    p = session.get(Problem, problem_id)
    if not p or not p.visible: raise HTTPException(404, "Problem not found")
    return {"id":p.id,"slug":p.slug,"title":p.title,"statement":p.statement,
            "difficulty":p.difficulty,"time_limit_ms":p.time_limit_ms,"memory_limit_mb":p.memory_limit_mb}

@app.get("/api/contests")
def contests(session: Session = Depends(get_session)):
    rows = session.exec(select(Contest)).all()
    now = datetime.now(timezone.utc)
    return [{"id":c.id,"title":c.title,"description":c.description,
             "start_at":c.start_at,"end_at":c.end_at,
             "status":"UPCOMING" if c.start_at > now else ("ENDED" if c.end_at < now else "LIVE"),
             "problem_count":len(c.problem_ids)} for c in rows]

@app.get("/api/contests/{contest_id}")
def contest_detail(contest_id: int, session: Session = Depends(get_session)):
    c = session.get(Contest, contest_id)
    if not c: raise HTTPException(404, "Contest not found")
    ps = [session.get(Problem, pid) for pid in c.problem_ids]
    return {"id":c.id,"title":c.title,"description":c.description,"start_at":c.start_at,
            "end_at":c.end_at,"problems":[{"id":p.id,"title":p.title,"difficulty":p.difficulty} for p in ps if p and p.visible]}

@app.post("/api/submit")
def submit(data: SubmitIn, user: User = Depends(current_user), session: Session = Depends(get_session)):
    p = session.get(Problem, data.problem_id)
    if not p or not p.visible: raise HTTPException(404, "Problem not found")
    if data.language not in ["cpp17","cpp20","python","java"]: raise HTTPException(400, "Unsupported language")
    contest = None
    if data.contest_id:
        contest = session.get(Contest, data.contest_id)
        now = datetime.now(timezone.utc)
        if contest and contest.start_at.tzinfo is None:
            contest.start_at = contest.start_at.replace(tzinfo=timezone.utc)
        if contest and contest.end_at.tzinfo is None:
            contest.end_at = contest.end_at.replace(tzinfo=timezone.utc)
        if not contest or not (contest.start_at <= now <= contest.end_at) or p.id not in contest.problem_ids:
            raise HTTPException(400, "Contest is not active or problem is not in contest")
    sub = Submission(user_id=user.id, problem_id=p.id, contest_id=data.contest_id,
                     language=data.language, source_code=data.source_code)
    session.add(sub); session.commit(); session.refresh(sub)
    verdict, ms, detail = run_submission(data.language, data.source_code, p.tests, p.time_limit_ms, p.memory_limit_mb)
    sub.verdict, sub.time_ms = verdict, ms
    sub.score = 100 if verdict == "AC" else 0
    session.add(sub); session.commit(); session.refresh(sub)
    return {"id":sub.id,"verdict":verdict,"score":sub.score,"time_ms":ms,"detail":detail}

@app.get("/api/submissions")
def submissions(user: User = Depends(current_user), session: Session = Depends(get_session)):
    rows = session.exec(select(Submission).where(Submission.user_id == user.id).order_by(Submission.created_at.desc()).limit(50)).all()
    return [{"id":s.id,"problem_id":s.problem_id,"contest_id":s.contest_id,"language":s.language,
             "verdict":s.verdict,"score":s.score,"time_ms":s.time_ms,"created_at":s.created_at} for s in rows]

@app.get("/api/leaderboard/{contest_id}")
def leaderboard(contest_id: int, session: Session = Depends(get_session)):
    c = session.get(Contest, contest_id)
    if not c: raise HTTPException(404, "Contest not found")
    rows = session.exec(select(Submission).where(Submission.contest_id == contest_id)).all()
    scores = {}
    for s in rows:
        entry = scores.setdefault(s.user_id, {"score":0,"solved":set(),"penalty":0})
        if s.verdict == "AC" and s.problem_id not in entry["solved"]:
            entry["solved"].add(s.problem_id); entry["score"] += 100
        entry["penalty"] += max(0, s.time_ms // 1000)
    result=[]
    for uid,e in scores.items():
        u=session.get(User,uid)
        result.append({"username":u.username if u else "unknown","score":e["score"],"solved":len(e["solved"]),"penalty":e["penalty"]})
    return sorted(result,key=lambda x:(-x["score"],x["penalty"]))

@app.post("/api/admin/problems")
def create_problem(data: ProblemIn, admin: User = Depends(admin_user), session: Session = Depends(get_session)):
    if session.exec(select(Problem).where(Problem.slug == data.slug)).first():
        raise HTTPException(409, "Slug already exists")
    p=Problem(**data.model_dump()); session.add(p); session.commit(); session.refresh(p)
    return {"id":p.id,"slug":p.slug}

@app.post("/api/admin/contests")
def create_contest(data: ContestIn, admin: User = Depends(admin_user), session: Session = Depends(get_session)):
    if data.end_at <= data.start_at: raise HTTPException(400,"end_at must be after start_at")
    for pid in data.problem_ids:
        if not session.get(Problem,pid): raise HTTPException(404,f"Problem {pid} not found")
    c=Contest(**data.model_dump()); session.add(c); session.commit(); session.refresh(c)
    return {"id":c.id,"title":c.title}

@app.get("/api/admin/submissions")
def all_submissions(admin: User = Depends(admin_user), session: Session = Depends(get_session)):
    rows=session.exec(select(Submission).order_by(Submission.created_at.desc()).limit(200)).all()
    return [{"id":s.id,"user_id":s.user_id,"problem_id":s.problem_id,"verdict":s.verdict,"language":s.language} for s in rows]
