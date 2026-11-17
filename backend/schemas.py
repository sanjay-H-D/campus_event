"""Pydantic validation and API response schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class CollegeCreate(BaseModel):
    college_name: str = Field(min_length=2, max_length=150)
    college_location: str = Field(min_length=2, max_length=150)


class CollegeResponse(CollegeCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain a lowercase letter.")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain an uppercase letter.")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain a number.")
        return value


class LoginCredentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=100)


class AdminRegister(Credentials):
    full_name: str = Field(min_length=2, max_length=100)
    college: CollegeCreate


class StudentRegister(Credentials):
    full_name: str = Field(min_length=2, max_length=100)
    college_name: str = Field(min_length=2, max_length=150)


class EventCreate(BaseModel):
    event_name: str = Field(min_length=2, max_length=150)
    description: str = Field(default="", max_length=2000)
    event_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    event_time: str = Field(min_length=2, max_length=30)
    duration: str = Field(min_length=2, max_length=60)
    venue: str = Field(min_length=2, max_length=150)
    category: str = Field(min_length=2, max_length=60)
    registration_fee: float = Field(default=0, ge=0, le=100000)
    maximum_seats: int = Field(gt=0, le=100000)


class EventResponse(EventCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    college_id: int
    college_name: str | None = None
    available_seats: int


class BookingResponse(BaseModel):
    id: int
    booking_reference: str
    booking_status: str
    booked_at: str
    event: EventResponse
    college: CollegeResponse
    student_name: str | None = None
    student_email: EmailStr | None = None


class DemoPaymentCreateRequest(BaseModel):
    event_id: int = Field(gt=0)


class DemoPaymentResponse(BaseModel):
    payment_id: int
    booking_id: int
    payment_reference: str
    amount: float
    currency: str
    event: EventResponse


class DemoPaymentRequest(BaseModel):
    payment_id: int = Field(gt=0)
    outcome: str = Field(pattern=r"^(successful|failed)$")


class PaymentResponse(BaseModel):
    id: int
    booking_id: int
    event_id: int
    payment_reference: str
    amount: float
    currency: str
    payment_status: str
    payment_method: str | None
    transaction_date: str | None
    event: EventResponse


class ParticipantProfile(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    college_name: str
