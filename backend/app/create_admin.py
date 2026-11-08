import getpass

from sqlalchemy import func

from .database import SessionLocal
from .models import User
from .security import hash_password


def main():
    name = input("Administrator name: ").strip()
    email = input("Administrator email: ").strip().lower()
    password = getpass.getpass("Administrator password (10+ characters): ")
    if len(name) < 2 or len(password) < 10:
        raise SystemExit("Name must have at least 2 characters and password at least 10.")
    db = SessionLocal()
    try:
        if db.query(User).filter(func.lower(User.email) == email).first():
            raise SystemExit("An account already uses this email.")
        admin = User(name=name, email=email, password_hash=hash_password(password), role="admin")
        db.add(admin)
        db.commit()
        print("Administrator account created.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
