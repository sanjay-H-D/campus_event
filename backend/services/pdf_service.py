"""PDF receipt and participant export generation."""

from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from ..database.models import Booking, Event, Payment, Student
from .exceptions import ValidationError


def _styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReceiptTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#183b56")))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    return styles


def _paragraph(value: object, style: str = "BodyText") -> Paragraph:
    return Paragraph(str(value), _styles()[style])


def payment_receipt(payment: Payment) -> bytes:
    if payment.payment_status != "Successful" or payment.gateway_payment_id is None:
        raise ValidationError("A receipt is available only for successful payments.")
    event = payment.event
    student = payment.student
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = _styles()
    story = [
        Paragraph("Campus Event Ticketing Engine", styles["ReceiptTitle"]),
        Spacer(1, 8),
        Paragraph("PAYMENT RECEIPT", styles["Heading2"]),
        Spacer(1, 6),
    ]
    rows = [
        ("Receipt number", f"REC-{payment.id:08d}"),
        ("Participant", student.full_name),
        ("Email", student.email),
        ("College", event.college.college_name),
        ("Event", event.event_name),
        ("Event date", event.event_date),
        ("Venue", event.venue),
        ("Booking ID", payment.booking.booking_reference),
        ("Payment ID", payment.gateway_payment_id),
        ("Registration fee", f"{payment.currency} {payment.amount:.2f}"),
        ("Payment date", payment.transaction_date.isoformat(sep=" ") if payment.transaction_date else ""),
        ("Payment method", payment.payment_method or "Razorpay"),
        ("Status", "SUCCESSFUL"),
    ]
    table = Table([[Paragraph(f"<b>{key}</b>"), Paragraph(value)] for key, value in rows], colWidths=[45 * mm, 115 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef4f8")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b7c8d4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))
    story.append(Paragraph("This receipt confirms successful payment for the event registration.", styles["Small"]))
    document.build(story)
    return output.getvalue()


def participant_list(event: Event, bookings: list[Booking], payments: list[Payment]) -> bytes:
    payment_by_booking = {item.booking_id: item for item in payments}
    successful = [item for item in payments if item.payment_status == "Successful"]
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = _styles()
    story = [
        Paragraph("Campus Event Ticketing Engine", styles["ReceiptTitle"]),
        Paragraph("Participant Payment List", styles["Heading2"]),
        Paragraph(
            f"<b>College:</b> {event.college.college_name}<br/><b>Event:</b> {event.event_name}<br/>"
            f"<b>Date:</b> {event.event_date} &nbsp; <b>Venue:</b> {event.venue}<br/>"
            f"<b>Category:</b> {event.category} &nbsp; <b>Maximum seats:</b> {event.maximum_seats}<br/>"
            f"<b>Confirmed participants:</b> {sum(item.booking_status == 'confirmed' for item in bookings)} &nbsp; "
            f"<b>Successful payments:</b> {len(successful)} &nbsp;"
            f"<b>Total collected:</b> INR {sum(item.amount for item in successful):.2f}",
            styles["BodyText"],
        ),
        Spacer(1, 8),
    ]
    data = [["No.", "Participant", "Email", "Booking ID", "Status", "Amount", "Booking date"]]
    for index, booking in enumerate(bookings, 1):
        payment = payment_by_booking.get(booking.id)
        data.append([
            str(index),
            booking.student.full_name,
            booking.student.email,
            booking.booking_reference,
            payment.payment_status if payment else "Not paid",
            f"{payment.currency} {payment.amount:.2f}" if payment else "INR 0.00",
            booking.booked_at.strftime("%Y-%m-%d %H:%M"),
        ])
    if len(data) == 1:
        data.append(["-", "No successful payments", "-", "-", "-", "-", "-"])
    table = Table(data, repeatRows=1, colWidths=[10 * mm, 29 * mm, 38 * mm, 25 * mm, 22 * mm, 22 * mm, 30 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#183b56")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b7c8d4")),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("LEADING", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7f9")]),
    ]))
    story.append(table)
    document.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    return output.getvalue()


def _page_number(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(A4[0] - 12 * mm, 8 * mm, f"Page {document.page}")
    canvas.restoreState()
