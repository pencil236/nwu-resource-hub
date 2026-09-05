from sqlalchemy import select

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import ProcessingJob, User
from app.services.deepseek import deepseek_client
from tests.helpers import auth_headers, register_user, upload_docx


def test_refresh_token_is_rotated_once(client):
    tokens = register_user(client, "refresh@school.edu.cn")
    first = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert first.status_code == 200
    replay = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "HTTP_401"


def test_unpublished_resource_is_private_and_job_is_recorded(client):
    owner = register_user(client, "owner2@school.edu.cn")
    visitor = register_user(client, "visitor@school.edu.cn")
    resource = upload_docx(client, auth_headers(owner))
    with SessionLocal() as db:
        job = db.scalar(select(ProcessingJob).where(ProcessingJob.resource_id == resource["id"]))
        assert job is not None
        assert job.status.value == "succeeded"
    hidden = client.get(f"/api/resources/{resource['id']}", headers=auth_headers(visitor))
    assert hidden.status_code == 404


def test_rejects_spoofed_file_signature_with_stable_error(client):
    tokens = register_user(client, "signature@school.edu.cn")
    response = client.post(
        "/api/resources",
        headers=auth_headers(tokens),
        data={"title": "伪造文件", "rights_confirmed": "true"},
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "文件内容与格式不匹配"
    assert response.headers["X-Request-ID"]


def test_report_admin_review_and_hide_flow(client):
    owner = register_user(client, "publisher@school.edu.cn")
    reporter = register_user(client, "reporter@school.edu.cn")
    admin = register_user(client, "admin@school.edu.cn")
    resource = upload_docx(client, auth_headers(owner), "被举报的资料")
    published = client.post(f"/api/resources/{resource['id']}/confirm", headers=auth_headers(owner))
    assert published.status_code == 200

    own_report = client.post(
        "/api/reports",
        headers=auth_headers(owner),
        json={"resource_id": resource["id"], "reason": "测试自我举报"},
    )
    assert own_report.status_code == 400

    report = client.post(
        "/api/reports",
        headers=auth_headers(reporter),
        json={"resource_id": resource["id"], "reason": "版权问题", "details": "疑似教材扫描"},
    )
    assert report.status_code == 201

    forbidden = client.get("/api/admin/reports", headers=auth_headers(reporter))
    assert forbidden.status_code == 403
    with SessionLocal() as db:
        admin_user = db.scalar(select(User).where(User.email == "admin@school.edu.cn"))
        admin_user.is_admin = True
        db.commit()

    reports = client.get("/api/admin/reports", headers=auth_headers(admin))
    assert reports.status_code == 200
    report_id = reports.json()[0]["id"]
    hidden = client.post(f"/api/admin/resources/{resource['id']}/hide", headers=auth_headers(admin))
    assert hidden.status_code == 200
    resolved = client.patch(
        f"/api/admin/reports/{report_id}",
        headers=auth_headers(admin),
        json={"status": "resolved", "resolution": "确认违规并下架"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"


def test_agent_fallback_only_returns_published_resources(client):
    owner = register_user(client, "agent-owner@school.edu.cn")
    resource = upload_docx(client, auth_headers(owner), "线性代数复习笔记")
    client.post(f"/api/resources/{resource['id']}/confirm", headers=auth_headers(owner))
    response = client.post(
        "/api/agent/chat", headers=auth_headers(owner), json={"message": "线性代数复习"}
    )
    assert response.status_code == 200
    assert response.json()["resources"][0]["resource"]["id"] == resource["id"]
    assert resource["id"] in response.json()["answer"]


def test_agent_executes_only_validated_search_tool(client, monkeypatch):
    owner = register_user(client, "tool-owner@school.edu.cn")
    resource = upload_docx(client, auth_headers(owner), "概率论考试资料")
    client.post(f"/api/resources/{resource['id']}/confirm", headers=auth_headers(owner))
    settings = get_settings()
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    turns = iter(
        [
            {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "search_resources",
                            "arguments": (
                                '{"query":"概率论考试","course":null,'
                                '"category":null,"file_type":null}'
                            ),
                        },
                    }
                ],
            },
            {"content": f"推荐《概率论考试资料》，资源 ID：{resource['id']}。"},
        ]
    )
    captured_messages = []

    def fake_turn(messages, _tools):
        captured_messages[:] = messages
        return next(turns)

    monkeypatch.setattr(deepseek_client, "agent_turn", fake_turn)
    response = client.post(
        "/api/agent/chat", headers=auth_headers(owner), json={"message": "找概率论考试资料"}
    )
    assert response.status_code == 200
    assert response.json()["resources"][0]["resource"]["id"] == resource["id"]
    assert any(message.get("role") == "tool" for message in captured_messages)
