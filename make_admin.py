import sys
from sqlmodel import Session, select
from app.database import create_db, engine
from app.models import User

if len(sys.argv) != 2:
    raise SystemExit("Usage: python scripts/make_admin.py USERNAME")
create_db()
with Session(engine) as session:
    user = session.exec(select(User).where(User.username == sys.argv[1])).first()
    if not user:
        raise SystemExit("User not found. Register on the website first.")
    user.is_admin = True
    session.add(user); session.commit()
    print(f"{user.username} is now an admin")
