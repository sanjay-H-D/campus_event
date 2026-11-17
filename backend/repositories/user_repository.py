"""Repository operations for users and colleges."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.models import Admin, College, Student


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_admin_by_email(self, email: str) -> Admin | None:
        return self.db.scalar(select(Admin).where(Admin.email == email))

    def get_admin(self, admin_id: int) -> Admin | None:
        return self.db.get(Admin, admin_id)

    def add_admin(self, admin: Admin) -> Admin:
        self.db.add(admin)
        return admin

    def get_student_by_email(self, email: str) -> Student | None:
        return self.db.scalar(select(Student).where(Student.email == email))

    def get_student(self, student_id: int) -> Student | None:
        return self.db.get(Student, student_id)

    def add_student(self, student: Student) -> Student:
        self.db.add(student)
        return student

    def get_college(self, college_id: int) -> College | None:
        return self.db.get(College, college_id)

    def find_college_by_name(self, college_name: str) -> College | None:
        return self.db.scalar(select(College).where(College.college_name.ilike(college_name)))

    def list_colleges(self, search: str | None, offset: int, limit: int) -> list[College]:
        statement = select(College).order_by(College.college_name).offset(offset).limit(limit)
        if search:
            statement = statement.where(College.college_name.ilike(f"%{search.strip()}%"))
        return list(self.db.scalars(statement))
