"""Usage: python -m app.scripts.create_admin admin@school.edu 'StrongPassword' 'Admin Name'"""
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Role, User

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    email, pwd = sys.argv[1].lower(), sys.argv[2]
    name = sys.argv[3] if len(sys.argv) > 3 else "Administrator"
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            sys.exit("User already exists")
        db.add(User(name=name, email=email, password_hash=hash_password(pwd), role=Role.admin))
        db.commit()
        print(f"Admin {email} created")
