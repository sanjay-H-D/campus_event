"""Registration and login business rules."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database.models import Admin, College, Student
from ..repositories.user_repository import UserRepository
from .exceptions import ConflictError, NotFoundError
from .security import create_access_token, hash_password, verify_password


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    def register_admin(self, full_name: str, email: str, password: str, college_name: str, college_location: str) -> Admin:
        if self.users.get_admin_by_email(email):
            raise ConflictError("An admin with this email already exists.")
        college = self.users.find_college_by_name(college_name)
        if college is None:
            college = College(college_name=college_name, college_location=college_location)
            self.db.add(college)
            self.db.flush()
        admin = Admin(full_name=full_name.strip(), email=email, password_hash=hash_password(password), college_id=college.id)
        self.users.add_admin(admin)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise ConflictError("Admin email or college already exists.") from error
        self.db.refresh(admin)
        return admin

    def login_admin(self, email: str, password: str) -> str:
        admin = self.users.get_admin_by_email(email)
        if admin is None or not verify_password(password, admin.password_hash):
            raise NotFoundError("Invalid admin email or password.")
        return create_access_token(admin.id, "admin")

    def register_participant(self, full_name: str, email: str, password: str, college_name: str) -> Student:
        if self.users.get_student_by_email(email):
            raise ConflictError("A participant with this email already exists.")
        student = Student(full_name=full_name.strip(), email=email, password_hash=hash_password(password), college_name=college_name.strip())
        self.users.add_student(student)
        try:
            self.db.commit()
        except IntegrityError as error:
            self.db.rollback()
            raise ConflictError("Participant email already exists.") from error
        self.db.refresh(student)
        return student

    def login_participant(self, email: str, password: str) -> str:
        student = self.users.get_student_by_email(email)
        if student is None or not verify_password(password, student.password_hash):
            raise NotFoundError("Invalid participant email or password.")
        return create_access_token(student.id, "participant")
