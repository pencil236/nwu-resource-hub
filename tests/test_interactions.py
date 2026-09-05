from tests.helpers import auth_headers, register_user, upload_docx


def _published_resource(client, owner_headers: dict[str, str]) -> dict:
    resource = upload_docx(client, owner_headers, "互动测试笔记")
    response = client.post(f"/api/resources/{resource['id']}/confirm", headers=owner_headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_like_is_idempotent_and_can_be_removed(client):
    owner = register_user(client, "like-owner@school.edu.cn")
    reader = register_user(client, "like-reader@school.edu.cn")
    resource = _published_resource(client, auth_headers(owner))
    headers = auth_headers(reader)

    first = client.post(f"/api/resources/{resource['id']}/likes", headers=headers)
    second = client.post(f"/api/resources/{resource['id']}/likes", headers=headers)
    assert first.status_code == 200
    assert second.json()["like_count"] == 1
    assert second.json()["liked_by_me"] is True

    listing = client.get("/api/resources", headers=headers)
    assert listing.json()[0]["like_count"] == 1
    assert listing.json()[0]["liked_by_me"] is True

    removed = client.delete(f"/api/resources/{resource['id']}/likes", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["like_count"] == 0
    assert removed.json()["liked_by_me"] is False


def test_comments_are_listed_and_protected(client):
    owner = register_user(client, "comment-owner@school.edu.cn")
    author = register_user(client, "comment-author@school.edu.cn")
    visitor = register_user(client, "comment-visitor@school.edu.cn")
    resource = _published_resource(client, auth_headers(owner))
    author_headers = auth_headers(author)

    created = client.post(
        f"/api/resources/{resource['id']}/comments",
        headers=author_headers,
        json={"content": "这份资料的例题很适合考前复习。"},
    )
    assert created.status_code == 201, created.text
    comment = created.json()
    assert comment["author_name"] == "comment-author"

    listing = client.get(
        f"/api/resources/{resource['id']}/comments", headers=auth_headers(visitor)
    )
    assert listing.status_code == 200
    assert listing.json()[0]["content"] == "这份资料的例题很适合考前复习。"

    forbidden = client.delete(
        f"/api/resources/{resource['id']}/comments/{comment['id']}",
        headers=auth_headers(visitor),
    )
    assert forbidden.status_code == 403

    deleted = client.delete(
        f"/api/resources/{resource['id']}/comments/{comment['id']}",
        headers=author_headers,
    )
    assert deleted.status_code == 204
    resource_view = client.get(f"/api/resources/{resource['id']}", headers=author_headers)
    assert resource_view.json()["comment_count"] == 0


def test_office_resource_has_authenticated_text_preview(client):
    owner = register_user(client, "preview-owner@school.edu.cn")
    headers = auth_headers(owner)
    resource = _published_resource(client, headers)

    preview = client.get(f"/api/resources/{resource['id']}/preview-text", headers=headers)
    assert preview.status_code == 200
    assert "高等数学" in preview.json()["text"]
    assert preview.json()["truncated"] is False

    binary_preview = client.get(f"/api/resources/{resource['id']}/preview", headers=headers)
    assert binary_preview.status_code == 415
