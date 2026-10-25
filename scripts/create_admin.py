import getpass

from app.db.session import SessionLocal
from app.db.models import User
from app.services.auth_service import hash_password


def main():
    email = input("Admin email: ").strip().lower()
    password = getpass.getpass("Admin password (12+ characters): ")

    if SessionLocal is None:
        raise RuntimeError("Database session factory is not configured.")

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            raise SystemExit("That email already exists.")

        user = User(
            email=email,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        print("Admin account created.")
    finally:
        db.close()


if __name__ == "__main__":
    main()