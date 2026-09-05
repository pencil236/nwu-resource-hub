from app.core.config import get_settings
from tests.helpers import auth_headers, docx_bytes, register_user, upload_docx


def _publish(client, headers: dict[str, str], resource: dict) -> dict:
    response = client.post(f"/api/resources/{resource['id']}/confirm", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_resource_metadata_filters_sort_and_reactions(client):
    owner = register_user(client, "extended-owner@school.edu.cn")
    reader = register_user(client, "extended-reader@school.edu.cn")
    owner_headers = auth_headers(owner)
    response = client.post(
        "/api/resources",
        headers=owner_headers,
        data={
            "title": "软件工程课程笔记",
            "resource_type": "个人笔记",
            "college": "信息科学与技术学院",
            "major": "软件工程",
            "course": "软件测试",
            "teacher": "Z 老师",
            "grade": "大三",
            "year": "2026",
            "is_anonymous": "false",
            "rights_confirmed": "true",
        },
        files={
            "file": (
                "testing.docx",
                docx_bytes("软件测试包括单元测试、集成测试和验收测试。"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 201, response.text
    resource = _publish(client, owner_headers, response.json())
    reader_headers = auth_headers(reader)

    filtered = client.get(
        "/api/resources",
        headers=reader_headers,
        params={
            "resource_type": "个人笔记",
            "college": "信息科学",
            "major": "软件工程",
            "course": "软件测试",
            "teacher": "Z",
            "grade": "大三",
            "year": 2026,
            "sort_by": "likes",
        },
    )
    assert filtered.status_code == 200
    assert filtered.json()[0]["id"] == resource["id"]
    assert filtered.json()[0]["owner_name"] == "extended-owner"

    liked = client.post(f"/api/resources/{resource['id']}/likes", headers=reader_headers)
    assert liked.json()["like_count"] == 1
    disliked = client.post(f"/api/resources/{resource['id']}/dislikes", headers=reader_headers)
    assert disliked.json()["like_count"] == 0
    assert disliked.json()["dislike_count"] == 1
    assert disliked.json()["liked_by_me"] is False
    assert disliked.json()["disliked_by_me"] is True


def test_anonymous_share_profile_and_onboarding(client):
    owner = register_user(client, "anonymous-owner@school.edu.cn")
    headers = auth_headers(owner)
    resource = upload_docx(client, headers, "匿名资料")
    with_anonymous = client.patch(
        f"/api/resources/{resource['id']}",
        headers=headers,
        json={"is_anonymous": True},
    )
    assert with_anonymous.status_code == 200
    _publish(client, headers, resource)

    listing = client.get("/api/resources", headers=headers)
    assert listing.json()[0]["owner_name"] == "匿名同学"
    profile = client.get(f"/api/users/{listing.json()[0]['owner_id']}", headers=headers)
    assert profile.json()["resource_count"] == 0

    me = client.get("/api/auth/me", headers=headers)
    assert me.json()["onboarding_completed"] is False
    completed = client.patch("/api/users/me/onboarding", headers=headers)
    assert completed.json()["onboarding_completed"] is True


def test_help_request_search_support_and_duplicate_hint(client):
    author = register_user(client, "help-author@school.edu.cn")
    supporter = register_user(client, "help-supporter@school.edu.cn")
    author_headers = auth_headers(author)
    response = client.post(
        "/api/help-requests",
        headers=author_headers,
        json={
            "title": "求高数期末真题",
            "description": "最好包含答案",
            "college": "数学学院",
            "major": "通用",
            "course": "高等数学",
        },
    )
    assert response.status_code == 201, response.text
    request_id = response.json()["id"]

    duplicate = client.post(
        "/api/help-requests",
        headers=auth_headers(supporter),
        json={"title": "求高数期末真题"},
    )
    assert duplicate.status_code == 409
    supported = client.post(
        f"/api/help-requests/{request_id}/supports", headers=auth_headers(supporter)
    )
    assert supported.json() == {"supported_by_me": True, "heat_count": 1}
    search = client.get(
        "/api/help-requests",
        headers=auth_headers(supporter),
        params={"q": "高数", "sort_by": "hot"},
    )
    assert search.json()[0]["supported_by_me"] is True
    assert search.json()[0]["heat_count"] == 1


def test_reports_auto_hide_at_configured_threshold(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "auto_hide_report_threshold", 2)
    owner = register_user(client, "threshold-owner@school.edu.cn")
    first = register_user(client, "threshold-first@school.edu.cn")
    second = register_user(client, "threshold-second@school.edu.cn")
    resource = upload_docx(client, auth_headers(owner), "自动下架测试")
    _publish(client, auth_headers(owner), resource)

    for reporter, reason in ((first, "版权问题"), (second, "内容不实")):
        response = client.post(
            "/api/reports",
            headers=auth_headers(reporter),
            json={"resource_id": resource["id"], "reason": reason},
        )
        assert response.status_code == 201
    listing = client.get("/api/resources", headers=auth_headers(first))
    assert all(item["id"] != resource["id"] for item in listing.json())
