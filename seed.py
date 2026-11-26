from datetime import datetime, timedelta, timezone
from sqlmodel import Session, select
from .models import Problem, Contest

def seed(session: Session):
    if not session.exec(select(Problem)).first():
        session.add(Problem(
            slug="sum-two-numbers", title="A. Sum Two Numbers",
            statement="รับจำนวนเต็มสองจำนวน a และ b แล้วพิมพ์ผลบวกของทั้งสองจำนวน\n\nInput: จำนวนเต็มสองจำนวน\nOutput: ผลบวก",
            difficulty="Easy", tests=[
                {"input":"1 2\n","output":"3\n"},
                {"input":"-5 8\n","output":"3\n"},
                {"input":"100 200\n","output":"300\n"}
            ], visible=True
        ))
    if not session.exec(select(Contest)).first():
        now = datetime.now(timezone.utc)
        session.add(Contest(title="Getting Started #001",
            description="การแข่งขันทดลองสำหรับเริ่มต้นใช้งาน",
            start_at=now-timedelta(hours=1), end_at=now+timedelta(days=30),
            problem_ids=[1]))
    session.commit()
