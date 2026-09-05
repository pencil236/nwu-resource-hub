from datetime import UTC, datetime, timedelta
from io import BytesIO

from docx import Document

from app.core.security import hash_value
from app.db import SessionLocal
from app.models import EmailCode


def register_user(client, email: str, code: str = "123456") -> dict:
    with SessionLocal() as db:
        db.add(
            EmailCode(
                email=email,
                code_hash=hash_value(code),
                expires_at=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
        db.commit()
    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "code": code,
            "password": "strong-password",
            "display_name": email.split("@", 1)[0],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def docx_bytes(text: str = "高等数学重点包括极限、导数与积分。") -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def upload_docx(client, headers: dict[str, str], title: str = "高数笔记") -> dict:
    response = client.post(
        "/api/resources",
        headers=headers,
        data={
            "title": title,
            "resource_type": "个人笔记",
            "course": "高等数学",
            "experience": "适合期末复习",
            "rights_confirmed": "true",
        },
        files={
            "file": (
                "notes.docx",
                docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
