import io

from tests.conftest import PNG
from tests.fakes import MP4


def _upload(user, pid, data: bytes, name: str = "ref.png"):
    return user.post(f"/api/projects/{pid}/assets", data={"file": (io.BytesIO(data), name)},
                     content_type="multipart/form-data")


def test_upload_detects_type_from_content(make_user):
    user = make_user()
    pid = user.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    # The extension says .txt but the content is a PNG; the content wins.
    response = _upload(user, pid, PNG, "trick.txt")
    assert response.status_code == 201
    asset = response.get_json()["asset"]
    assert asset["mime_type"] == "image/png" and asset["kind"] == "image"
    assert asset["original_filename"] == "trick.txt"

    video = _upload(user, pid, MP4, "clip.mp4").get_json()["asset"]
    assert video["kind"] == "video"


def test_upload_rejects_disguised_and_empty_files(make_user):
    user = make_user()
    pid = user.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    html = _upload(user, pid, b"<html><script>alert(1)</script></html>", "image.png")
    assert html.status_code == 415
    assert _upload(user, pid, b"", "empty.png").status_code == 422
    exe = _upload(user, pid, b"MZ\x90\x00" + b"\x00" * 100, "photo.jpg")
    assert exe.status_code == 415


def test_upload_size_limit(app, make_user):
    user = make_user()
    pid = user.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    app.config["MAX_UPLOAD_MB"] = 1
    try:
        response = _upload(user, pid, PNG + b"\x00" * (1024 * 1024 + 10))
    finally:
        app.config["MAX_UPLOAD_MB"] = 50
    assert response.status_code == 413
    assert response.get_json()["error"]["code"] == "file_too_large"


def test_path_traversal_filename_is_neutralised(make_user):
    user = make_user()
    pid = user.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    asset = _upload(user, pid, PNG, "../../etc/passwd.png").get_json()["asset"]
    assert asset["original_filename"] == "passwd.png"


def test_signed_url_serves_file_and_expires(app, make_user, client):
    user = make_user()
    pid = user.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    asset = _upload(user, pid, PNG).get_json()["asset"]
    url = user.get(f"/api/assets/{asset['id']}/url").get_json()["url"]
    served = client.get(url)
    assert served.status_code == 200
    assert served.data == PNG
    assert served.headers["Content-Type"] == "image/png"
    tampered = client.get(url[:-3] + "abc")
    assert tampered.status_code == 403


def test_cross_user_asset_access_is_blocked(make_user):
    owner, intruder = make_user(), make_user()
    pid = owner.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    asset = _upload(owner, pid, PNG).get_json()["asset"]
    aid = asset["id"]
    assert intruder.get(f"/api/assets/{aid}").status_code == 404
    assert intruder.get(f"/api/assets/{aid}/url").status_code == 404
    assert intruder.patch(f"/api/assets/{aid}", json={"display_name": "mine"}).status_code == 404
    assert intruder.delete(f"/api/assets/{aid}").status_code == 404
    assert _upload(intruder, pid, PNG).status_code == 404
    # Nor can an intruder attach someone else's asset to their own character.
    their_pid = intruder.post("/api/projects", json={"title": "Mine"}).get_json()["project"]["id"]
    response = intruder.post(f"/api/projects/{their_pid}/characters",
                             json={"name": "Thief", "reference_asset_id": aid})
    assert response.status_code == 404


def test_delete_asset_removes_file(app, make_user):
    user = make_user()
    pid = user.post("/api/projects", json={"title": "P"}).get_json()["project"]["id"]
    asset = _upload(user, pid, PNG).get_json()["asset"]
    with app.app_context():
        from app.extensions import db
        from app.models import Asset
        from app.storage.backends import get_storage

        key = db.session.get(Asset, asset["id"]).storage_key
        assert get_storage().exists(key)
    assert user.delete(f"/api/assets/{asset['id']}").status_code == 204
    with app.app_context():
        assert not get_storage().exists(key)
