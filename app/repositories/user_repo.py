from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models import User


def get_user_by_id(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()


def create_user(
    db: Session,
    username: str,
    email: str,
    hashed_password: str
):
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def update_user_last_seen(db: Session, user: User):
    user.last_seen_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(user)

    return user