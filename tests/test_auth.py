def admin_payload(email: str, college: str = "Test College") -> dict:
    return {
        "full_name": "Test Admin",
        "email": email,
        "password": "StrongPass123",
        "college": {"college_name": college, "college_location": "Test City"},
    }


def participant_payload(email: str) -> dict:
    return {
        "full_name": "Test Participant",
        "email": email,
        "password": "StrongPass123",
        "college_name": "Student College",
    }


def test_admin_registration_login_and_duplicates(client):
    assert client.post("/api/admin/register", json=admin_payload("admin@example.com")).status_code == 201
    assert client.post("/api/admin/register", json=admin_payload("admin@example.com")).status_code == 409
    login = client.post("/api/admin/login", json={"email": "admin@example.com", "password": "StrongPass123"})
    assert login.status_code == 200 and login.json()["role"] == "admin"
    assert client.post("/api/admin/login", json={"email": "admin@example.com", "password": "wrongpass"}).status_code == 401


def test_participant_registration_login_and_role_protection(client):
    assert client.post("/api/participant/register", json=participant_payload("student@example.com")).status_code == 201
    assert client.post("/api/participant/register", json=participant_payload("student@example.com")).status_code == 409
    login = client.post("/api/participant/login", json={"email": "student@example.com", "password": "StrongPass123"})
    assert login.status_code == 200 and login.json()["role"] == "participant"
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/admin/profile", headers=headers).status_code == 403
    assert client.post("/api/admin/register", json=admin_payload("other-admin@example.com")).status_code == 201
    admin_login = client.post(
        "/api/admin/login",
        json={"email": "other-admin@example.com", "password": "StrongPass123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    assert client.get("/api/participant/profile", headers=admin_headers).status_code == 403
