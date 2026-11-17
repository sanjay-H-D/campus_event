import hashlib
import hmac

from .test_auth import admin_payload, participant_payload
from .test_events import event_payload


def _admin_headers(client, email="payment-admin@example.com", college="Payment College"):
    client.post("/api/admin/register", json=admin_payload(email, college))
    result = client.post("/api/admin/login", json={"email": email, "password": "StrongPass123"})
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


def _participant_headers(client, email="payment-student@example.com"):
    client.post("/api/participant/register", json=participant_payload(email))
    result = client.post("/api/participant/login", json={"email": email, "password": "StrongPass123"})
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


def test_payment_order_signature_receipt_and_access_control(client, monkeypatch):
    secret = "payment-test-secret"
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", secret)
    monkeypatch.setattr(
        "backend.services.payment_gateway.RazorpayGateway.create_order",
        lambda self, amount_paise, receipt: {"id": "order_test_123"},
    )
    admin_headers = _admin_headers(client)
    event = client.post("/api/admin/events", headers=admin_headers, json=event_payload(seats=1)).json()
    student_headers = _participant_headers(client)

    order = client.post("/api/payments/create-order", headers=student_headers, json={"event_id": event["id"]})
    assert order.status_code == 200
    order_data = order.json()
    signature = hmac.new(
        secret.encode(), f"{order_data['order_id']}|pay_test_123".encode(), hashlib.sha256
    ).hexdigest()
    verified = client.post(
        "/api/payments/verify",
        headers=student_headers,
        json={
            "razorpay_order_id": order_data["order_id"],
            "razorpay_payment_id": "pay_test_123",
            "razorpay_signature": signature,
        },
    )
    assert verified.status_code == 200
    assert verified.json()["payment_status"] == "Successful"
    assert client.get("/api/payments/my-payments", headers=student_headers).json()[0]["payment_status"] == "Successful"
    receipt = client.get(f"/api/participant/receipts/{order_data['payment_id']}/download", headers=student_headers)
    assert receipt.status_code == 200 and receipt.content.startswith(b"%PDF")
    assert client.get(f"/api/participant/receipts/{order_data['payment_id']}/download").status_code == 401
    participant_pdf = client.get(f"/api/admin/events/{event['id']}/participants/pdf", headers=admin_headers)
    assert participant_pdf.status_code == 200 and participant_pdf.content.startswith(b"%PDF")
    other_admin = _admin_headers(client, "other-payment-admin@example.com", "Other Payment College")
    assert client.get(f"/api/admin/events/{event['id']}/participants/pdf", headers=other_admin).status_code == 404


def test_invalid_signature_releases_reserved_seat(client, monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "payment-test-secret")
    order_ids = iter(["order_test_failed", "order_test_retry"])
    monkeypatch.setattr(
        "backend.services.payment_gateway.RazorpayGateway.create_order",
        lambda self, amount_paise, receipt: {"id": next(order_ids)},
    )
    admin_headers = _admin_headers(client, "failed-admin@example.com", "Failed College")
    event = client.post("/api/admin/events", headers=admin_headers, json=event_payload(seats=1)).json()
    student_headers = _participant_headers(client, "failed-student@example.com")
    order = client.post("/api/payments/create-order", headers=student_headers, json={"event_id": event["id"]}).json()
    result = client.post(
        "/api/payments/verify",
        headers=student_headers,
        json={
            "razorpay_order_id": order["order_id"],
            "razorpay_payment_id": "pay_bad",
            "razorpay_signature": "invalid",
        },
    )
    assert result.status_code == 400
    assert client.get(f"/api/events/{event['id']}").json()["available_seats"] == 1
    retry = client.post("/api/payments/create-order", headers=student_headers, json={"event_id": event["id"]})
    assert retry.status_code == 200
