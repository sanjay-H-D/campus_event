from .test_auth import admin_payload, participant_payload
from .test_events import event_payload


def test_duplicate_and_capacity_booking(client):
    client.post("/api/admin/register", json=admin_payload("owner@example.com", "Booking College"))
    admin_login = client.post("/api/admin/login", json={"email": "owner@example.com", "password": "StrongPass123"})
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    event = client.post("/api/admin/events", headers=admin_headers, json=event_payload(seats=1)).json()
    client.post("/api/participant/register", json=participant_payload("first@example.com"))
    first_login = client.post("/api/participant/login", json={"email": "first@example.com", "password": "StrongPass123"})
    first_headers = {"Authorization": f"Bearer {first_login.json()['access_token']}"}
    booking = client.post(f"/api/events/{event['id']}/book", headers=first_headers)
    assert booking.status_code == 201 and booking.json()["booking_reference"].startswith("CE-")
    assert client.post(f"/api/events/{event['id']}/book", headers=first_headers).status_code == 409
    client.post("/api/participant/register", json=participant_payload("second@example.com"))
    second_login = client.post("/api/participant/login", json={"email": "second@example.com", "password": "StrongPass123"})
    second_headers = {"Authorization": f"Bearer {second_login.json()['access_token']}"}
    assert client.post(f"/api/events/{event['id']}/book", headers=second_headers).status_code == 409
    history = client.get("/api/participant/bookings", headers=first_headers)
    assert history.status_code == 200 and len(history.json()) == 1
