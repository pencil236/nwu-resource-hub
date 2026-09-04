from datetime import UTC, datetime, timedelta

from app.core.security import hash_value
from app.db import SessionLocal
from app.models import EmailCode


def test_rejects_non_campus_email(client):
    response = client.post("/api/auth/register-code", json={"email": "student@gmail.com"})
    assert response.status_code == 400


def test_register_login_and_current_user(client):
    with SessionLocal() as db:
        db.add(
            EmailCode(
                email="alice@school.edu.cn",
                code_hash=hash_value("123456"),
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
        db.commit()

    response = client.post(
        "/api/auth/register",
        json={
            "email": "alice@school.edu.cn",
            "code": "123456",
            "password": "strong-password",
            "display_name": "Alice",
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "alice@school.edu.cn"

    response = client.post(
        "/api/auth/login",
        json={"email": "alice@school.edu.cn", "password": "strong-password"},
    )
    assert response.status_code == 200
