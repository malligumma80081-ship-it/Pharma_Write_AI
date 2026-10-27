import argparse
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import User
from app.db.session import SessionLocal

ROLE_ALIASES = {
    "writer": "writer",
    "team_leader": "reviewer",
    "reviewer": "reviewer",
    "project_manager": "project_manager",
    "admin": "admin",
}
ROLE_LABELS = {
    "writer": "Writer",
    "reviewer": "Team Leader",
    "project_manager": "Project Manager",
    "admin": "Administrator",
}


def set_user_role(db: Session, email: str, role: str) -> User:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("Email address is required.")
    if role not in ROLE_ALIASES:
        raise ValueError(
            "Role must be writer, team_leader, project_manager, or admin."
        )

    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        raise ValueError(f"No account found for {normalized_email}.")

    user.role = ROLE_ALIASES[role]
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(user)
    return user


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set an existing PharmaWrite account's role."
    )
    parser.add_argument("email", help="Email address of the existing account")
    parser.add_argument(
        "role",
        choices=ROLE_ALIASES,
        help=(
            "writer, team_leader, project_manager, or admin "
            "(admin is reserved for administrators)"
        ),
    )
    args = parser.parse_args()

    if SessionLocal is None:
        parser.error("DATABASE_URL is not configured.")

    try:
        with SessionLocal() as db:
            user = set_user_role(db, args.email, args.role)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Updated {user.email} role to {ROLE_LABELS[user.role]}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
