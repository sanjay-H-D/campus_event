"""FastAPI presentation layer for the Campus Event Ticketing Engine."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import get_setting
from .database import get_db
from .database.initialization import initialize_database
from .database.models import Admin, Booking, College, Event, Student
from .presentation.dependencies import get_current_identity, require_admin, require_participant
from .schemas import (
    AdminRegister,
    BookingResponse,
    CollegeResponse,
    EventCreate,
    EventResponse,
    LoginCredentials,
    PaymentOrderRequest,
    PaymentOrderResponse,
    PaymentFailureRequest,
    PaymentResponse,
    PaymentVerifyRequest,
    ParticipantProfile,
    StudentRegister,
)
from .services.auth_service import AuthService
from .services.booking_service import BookingService
from .services.event_service import EventService
from .services.exceptions import ConflictError, NotFoundError, ValidationError
from .services.exceptions import ConfigurationError
from .services.payment_service import PaymentService
from .services.pdf_service import participant_list, payment_receipt

app = FastAPI(title="Campus Event Ticketing Engine", version="3.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.mount(
    "/frontend",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend", html=True),
    name="frontend",
)


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def event_response(event: Event) -> EventResponse:
    response = EventResponse.model_validate(event)
    response.college_name = event.college.college_name
    return response


def booking_response(booking: Booking, include_student: bool = False) -> dict:
    result = {
        "id": booking.id,
        "booking_reference": booking.booking_reference,
        "booking_status": booking.booking_status,
        "booked_at": booking.booked_at.isoformat(),
        "event": event_response(booking.event),
        "college": CollegeResponse.model_validate(booking.event.college),
    }
    if include_student:
        result["student_name"] = booking.student.full_name
        result["student_email"] = booking.student.email
    return result


def handle_service_error(error: Exception) -> None:
    if isinstance(error, ConflictError):
        raise HTTPException(status_code=409, detail=str(error)) from error
    if isinstance(error, NotFoundError):
        raise HTTPException(status_code=404, detail=str(error)) from error
    if isinstance(error, ValidationError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    if isinstance(error, ConfigurationError):
        raise HTTPException(status_code=503, detail=str(error)) from error
    raise error


@app.get("/", include_in_schema=False)
def home() -> RedirectResponse:
    return RedirectResponse(url="/frontend/index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/admin/register", status_code=201)
def register_admin(payload: AdminRegister, db: Annotated[Session, Depends(get_db)]) -> dict:
    try:
        admin = AuthService(db).register_admin(
            full_name=payload.full_name,
            email=str(payload.email).lower(),
            password=payload.password,
            college_name=payload.college.college_name,
            college_location=payload.college.college_location,
        )
    except (ConflictError, NotFoundError, ValidationError) as error:
        handle_service_error(error)
    return {"message": "Admin registration successful.", "admin_id": admin.id}


@app.post("/api/admin/login")
def login_admin(payload: LoginCredentials, db: Annotated[Session, Depends(get_db)]) -> dict:
    try:
        token = AuthService(db).login_admin(str(payload.email).lower(), payload.password)
    except NotFoundError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return {"access_token": token, "token_type": "bearer", "role": "admin"}


@app.post("/api/participant/register", status_code=201)
def register_participant(payload: StudentRegister, db: Annotated[Session, Depends(get_db)]) -> dict:
    try:
        student = AuthService(db).register_participant(
            full_name=payload.full_name,
            email=str(payload.email).lower(),
            password=payload.password,
            college_name=payload.college_name,
        )
    except (ConflictError, NotFoundError, ValidationError) as error:
        handle_service_error(error)
    return {"message": "Participant registration successful.", "participant_id": student.id}


@app.post("/api/participant/login")
def login_participant(payload: LoginCredentials, db: Annotated[Session, Depends(get_db)]) -> dict:
    try:
        token = AuthService(db).login_participant(str(payload.email).lower(), payload.password)
    except NotFoundError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    return {"access_token": token, "token_type": "bearer", "role": "participant"}


@app.get("/api/admin/profile")
def admin_profile(admin: Annotated[Admin, Depends(require_admin)]) -> dict:
    return {
        "id": admin.id,
        "full_name": admin.full_name,
        "email": admin.email,
        "college": CollegeResponse.model_validate(admin.college),
    }


@app.get("/api/participant/profile", response_model=ParticipantProfile)
def participant_profile(student: Annotated[Student, Depends(require_participant)]) -> Student:
    return student


@app.get("/api/auth/me")
def current_user(identity: Annotated[tuple[Admin | Student, str], Depends(get_current_identity)]) -> dict:
    user, role = identity
    return {"role": role, "id": user.id, "full_name": user.full_name}


@app.get("/api/colleges", response_model=list[CollegeResponse])
def list_colleges(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[College]:
    return EventService(db).list_colleges(search, offset, limit)


def event_filters(
    db: Session,
    college_id: int | None,
    search: str | None,
    category: str | None,
    event_date: str | None,
    offset: int,
    limit: int,
) -> list[Event]:
    try:
        PaymentService(db).release_expired()
        return EventService(db).list_public(search, category, event_date, college_id, offset, limit)
    except (ConflictError, NotFoundError, ValidationError) as error:
        handle_service_error(error)
    return []


@app.get("/api/events", response_model=list[EventResponse])
def list_events(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=60),
    event_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[Event]:
    return event_filters(db, None, search, category, event_date, offset, limit)


@app.get("/api/colleges/{college_id}/events", response_model=list[EventResponse])
def college_events(
    college_id: int,
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=60),
    event_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[Event]:
    return event_filters(db, college_id, search, category, event_date, offset, limit)


@app.get("/api/events/{event_id}", response_model=EventResponse)
def get_event(event_id: int, db: Annotated[Session, Depends(get_db)]) -> Event:
    try:
        return EventService(db).get_public(event_id)
    except (ConflictError, NotFoundError, ValidationError) as error:
        handle_service_error(error)
    raise RuntimeError("Unreachable")


@app.post("/api/admin/events", response_model=EventResponse, status_code=201)
def create_event(payload: EventCreate, admin: Annotated[Admin, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> Event:
    return EventService(db).create(admin, payload.model_dump())


@app.get("/api/admin/events", response_model=list[EventResponse])
def admin_events(admin: Annotated[Admin, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> list[Event]:
    return EventService(db).list_owned(admin)


@app.get("/api/admin/events/{event_id}", response_model=EventResponse)
def admin_event(event_id: int, admin: Annotated[Admin, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> Event:
    try:
        return EventService(db).get_owned(admin, event_id)
    except (ConflictError, NotFoundError, ValidationError) as error:
        handle_service_error(error)
    raise RuntimeError("Unreachable")


@app.put("/api/admin/events/{event_id}", response_model=EventResponse)
def update_event(event_id: int, payload: EventCreate, admin: Annotated[Admin, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> Event:
    try:
        return EventService(db).update(admin, event_id, payload.model_dump())
    except (ConflictError, NotFoundError, ValidationError) as error:
        handle_service_error(error)
    raise RuntimeError("Unreachable")


@app.delete("/api/admin/events/{event_id}", status_code=204)
def delete_event(event_id: int, admin: Annotated[Admin, Depends(require_admin)], db: Annotated[Session, Depends(get_db)]) -> None:
    try:
        EventService(db).delete(admin, event_id)
    except (ConflictError, NotFoundError, ValidationError) as error:
        handle_service_error(error)


@app.get("/api/admin/events/{event_id}/participants")
def event_participants(
    event_id: int,
    admin: Annotated[Admin, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict:
    try:
        event, bookings = BookingService(db).participants(admin, event_id, offset, limit)
        payments = PaymentService(db).payments.list_for_event(event.id)
    except (ConflictError, NotFoundError, ValidationError, ConfigurationError) as error:
        handle_service_error(error)
    payment_by_booking = {item.booking_id: item for item in payments}
    return {
        "event": event_response(event),
        "total_bookings": event.maximum_seats - event.available_seats,
        "available_seats": event.available_seats,
        "participants": [
            {
                **booking_response(item, True),
                "payment_status": payment_by_booking[item.id].payment_status if item.id in payment_by_booking else "Not paid",
                "payment_amount": payment_by_booking[item.id].amount if item.id in payment_by_booking else 0,
            }
            for item in bookings
        ],
    }


@app.get("/api/admin/events/{event_id}/participants/pdf")
def download_participant_list(
    event_id: int,
    admin: Annotated[Admin, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    try:
        event, payments = PaymentService(db).list_for_admin_event(admin.college_id, event_id)
        _, bookings = BookingService(db).participants(admin, event_id, 0, 100000)
        document = participant_list(event, bookings, payments)
    except (ConflictError, NotFoundError, ValidationError, ConfigurationError) as error:
        handle_service_error(error)
    safe_event_name = "".join(char if char.isalnum() else "-" for char in event.event_name).strip("-").lower()
    return Response(
        content=document,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="participants-{safe_event_name or event.id}.pdf"'},
    )


@app.post("/api/events/{event_id}/book", response_model=BookingResponse, status_code=201)
def book_event(event_id: int, student: Annotated[Student, Depends(require_participant)], db: Annotated[Session, Depends(get_db)]) -> dict:
    try:
        return booking_response(BookingService(db).book(student, event_id))
    except (ConflictError, NotFoundError, ValidationError) as error:
        handle_service_error(error)
    raise RuntimeError("Unreachable")


@app.get("/api/participant/bookings", response_model=list[BookingResponse])
def participant_bookings(student: Annotated[Student, Depends(require_participant)], db: Annotated[Session, Depends(get_db)]) -> list[dict]:
    return [booking_response(item) for item in BookingService(db).list_for_student(student)]


def payment_response(payment) -> dict:
    return {
        "id": payment.id,
        "booking_id": payment.booking_id,
        "event_id": payment.event_id,
        "gateway_payment_id": payment.gateway_payment_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "payment_status": payment.payment_status,
        "payment_method": payment.payment_method,
        "transaction_date": payment.transaction_date.isoformat() if payment.transaction_date else None,
        "event": event_response(payment.event),
    }


@app.post("/api/payments/create-order", response_model=PaymentOrderResponse)
def create_payment_order(
    payload: PaymentOrderRequest,
    student: Annotated[Student, Depends(require_participant)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        payment, event = PaymentService(db).create_order(student, payload.event_id)
    except (ConflictError, NotFoundError, ValidationError, ConfigurationError) as error:
        handle_service_error(error)
    return {
        "payment_id": payment.id,
        "booking_id": payment.booking_id,
        "order_id": payment.gateway_order_id,
        "amount": payment.amount,
        "amount_paise": PaymentService._amount_paise(payment.amount),
        "currency": payment.currency,
        "key_id": get_setting("RAZORPAY_KEY_ID"),
        "event": event_response(event),
    }


@app.post("/api/payments/verify", response_model=PaymentResponse)
def verify_payment(
    payload: PaymentVerifyRequest,
    student: Annotated[Student, Depends(require_participant)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        payment = PaymentService(db).verify(
            student,
            payload.razorpay_order_id,
            payload.razorpay_payment_id,
            payload.razorpay_signature,
        )
    except (ConflictError, NotFoundError, ValidationError, ConfigurationError) as error:
        handle_service_error(error)
    return payment_response(payment)


@app.post("/api/payments/fail", response_model=PaymentResponse)
def fail_payment(
    payload: PaymentFailureRequest,
    student: Annotated[Student, Depends(require_participant)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    try:
        payment = PaymentService(db).fail(student, payload.razorpay_order_id)
    except (ConflictError, NotFoundError, ValidationError, ConfigurationError) as error:
        handle_service_error(error)
    return payment_response(payment)


@app.get("/api/payments/my-payments", response_model=list[PaymentResponse])
def my_payments(
    student: Annotated[Student, Depends(require_participant)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    return [payment_response(item) for item in PaymentService(db).list_for_student(student)]


def receipt_download(payment_id: int, student: Student, db: Session) -> Response:
    try:
        payment = PaymentService(db).get_owned_payment(student, payment_id)
        document = payment_receipt(payment)
    except (ConflictError, NotFoundError, ValidationError, ConfigurationError) as error:
        handle_service_error(error)
    return Response(
        content=document,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="payment-receipt-{payment_id}.pdf"'},
    )


@app.get("/api/payments/{payment_id}/receipt")
@app.get("/api/participant/receipts/{payment_id}/download")
def download_payment_receipt(
    payment_id: int,
    student: Annotated[Student, Depends(require_participant)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    return receipt_download(payment_id, student, db)
