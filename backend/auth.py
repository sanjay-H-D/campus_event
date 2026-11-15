"""Argon2 password hashing and JWT role authentication."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import get_db
from .models import Admin, Student

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be configured in the environment or .env file.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/login")
password_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(subject: int, role: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(subject), "role": role, "exp": expires}, SECRET_KEY, algorithm=ALGORITHM)


def get_current_identity(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> tuple[Admin | Student, str]:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload: dict[str, Any] = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject, role = payload.get("sub"), payload.get("role")
        if not subject or role not in {"admin", "participant"}:
            raise unauthorized
        model = Admin if role == "admin" else Student
        user = db.get(model, int(subject))
    except (JWTError, ValueError) as error:
        raise unauthorized from error
    if user is None:
        raise unauthorized
    return user, role


def require_admin(identity: tuple[Admin | Student, str] = Depends(get_current_identity)) -> Admin:
    user, role = identity
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin access is required.")
    return user  # type: ignore[return-value]


def require_participant(identity: tuple[Admin | Student, str] = Depends(get_current_identity)) -> Student:
    user, role = identity
    if role != "participant":
        raise HTTPException(status_code=403, detail="Participant access is required.")
    return user  # type: ignore[return-value]
