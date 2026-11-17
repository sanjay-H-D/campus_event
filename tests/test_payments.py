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


def test_demo_payment_success_receipt_and_access_control(client):
    admin_headers = _admin_headers(client)
    event = client.post("/api/admin/events", headers=admin_headers, json=event_payload(seats=1, fee=125)).json()
    student_headers = _participant_headers(client)

    created = client.post(
        "/api/payments/create-demo-payment",
        headers=student_headers,
        json={"event_id": event["id"]},
    )
    assert created.status_code == 200
    payment = created.json()
    assert payment["amount"] == 125

    simulated = client.post(
        "/api/payments/simulate",
        headers=student_headers,
        json={"payment_id": payment["payment_id"], "outcome": "successful"},
    )
    assert simulated.status_code == 200
    assert simulated.json()["payment_status"] == "Successful"
    assert client.get(f"/api/events/{event['id']}").json()["available_seats"] == 0

    history = client.get("/api/payments/my-payments", headers=student_headers)
    assert history.status_code == 200
    assert history.json()[0]["payment_reference"].startswith("DEMO-")
    receipt = client.get(f"/api/participant/receipts/{payment['payment_id']}/download", headers=student_headers)
    assert receipt.status_code == 200 and receipt.content.startswith(b"%PDF")
    assert client.get(f"/api/participant/receipts/{payment['payment_id']}/download").status_code == 401

    participant_pdf = client.get(f"/api/admin/events/{event['id']}/participants/pdf", headers=admin_headers)
    assert participant_pdf.status_code == 200 and participant_pdf.content.startswith(b"%PDF")
    other_admin = _admin_headers(client, "other-payment-admin@example.com", "Other Payment College")
    assert client.get(f"/api/admin/events/{event['id']}/participants/pdf", headers=other_admin).status_code == 404


def test_failed_demo_payment_releases_seat_and_allows_retry(client):
    admin_headers = _admin_headers(client, "failed-admin@example.com", "Failed College")
    event = client.post("/api/admin/events", headers=admin_headers, json=event_payload(seats=1, fee=75)).json()
    student_headers = _participant_headers(client, "failed-student@example.com")

    created = client.post(
        "/api/payments/create-demo-payment",
        headers=student_headers,
        json={"event_id": event["id"]},
    ).json()
    failed = client.post(
        "/api/payments/simulate",
        headers=student_headers,
        json={"payment_id": created["payment_id"], "outcome": "failed"},
    )
    assert failed.status_code == 200
    assert failed.json()["payment_status"] == "Failed"
    assert client.get(f"/api/events/{event['id']}").json()["available_seats"] == 1

    retry = client.post(
        "/api/payments/create-demo-payment",
        headers=student_headers,
        json={"event_id": event["id"]},
    )
    assert retry.status_code == 200
    assert retry.json()["payment_id"] != created["payment_id"]


def test_duplicate_successful_payment_is_rejected(client):
    admin_headers = _admin_headers(client, "duplicate-admin@example.com", "Duplicate College")
    event = client.post("/api/admin/events", headers=admin_headers, json=event_payload(seats=2, fee=50)).json()
    student_headers = _participant_headers(client, "duplicate-student@example.com")
    created = client.post(
        "/api/payments/create-demo-payment",
        headers=student_headers,
        json={"event_id": event["id"]},
    ).json()
    assert client.post(
        "/api/payments/simulate",
        headers=student_headers,
        json={"payment_id": created["payment_id"], "outcome": "successful"},
    ).status_code == 200
    duplicate = client.post(
        "/api/payments/create-demo-payment",
        headers=student_headers,
        json={"event_id": event["id"]},
    )
    assert duplicate.status_code == 409
