"""FastAPI authentication dependencies."""

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..database import get_db
from ..database.models import Admin, Student
from ..services.security import ALGORITHM, SECRET_KEY, create_access_token, hash_password, verify_password
from ..repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/login")


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
        repository = UserRepository(db)
        user = repository.get_admin(int(subject)) if role == "admin" else repository.get_student(int(subject))
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


__all__ = [
    "create_access_token",
    "get_current_identity",
    "hash_password",
    "require_admin",
    "require_participant",
    "verify_password",
]
