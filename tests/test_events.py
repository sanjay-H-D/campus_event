from .test_auth import admin_payload


def login_admin(client, email: str, college: str) -> dict:
    client.post("/api/admin/register", json=admin_payload(email, college))
    result = client.post("/api/admin/login", json={"email": email, "password": "StrongPass123"})
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


def event_payload(name="Campus Workshop", seats=2, fee=25):
    return {
        "event_name": name,
        "description": "A test event",
        "event_date": "2099-12-30",
        "event_time": "10:00 AM",
        "duration": "2 hours",
        "venue": "Main Hall",
        "category": "Workshop",
        "registration_fee": fee,
        "maximum_seats": seats,
    }


def test_event_visibility_ownership_and_soft_delete(client):
    admin_one = login_admin(client, "one@example.com", "College One")
    admin_two = login_admin(client, "two@example.com", "College Two")
    created = client.post("/api/admin/events", headers=admin_one, json=event_payload())
    assert created.status_code == 201
    event_id = created.json()["id"]
    assert client.get("/api/events").json()[0]["event_name"] == "Campus Workshop"
    assert client.put(f"/api/admin/events/{event_id}", headers=admin_two, json=event_payload("Not allowed")).status_code == 404
    assert client.delete(f"/api/admin/events/{event_id}", headers=admin_two).status_code == 404
    assert client.delete(f"/api/admin/events/{event_id}", headers=admin_one).status_code == 204
    assert client.get("/api/events").json() == []
