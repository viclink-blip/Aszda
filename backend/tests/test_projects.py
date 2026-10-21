def test_project_crud(make_user):
    user = make_user()
    created = user.post("/api/projects", json={"title": "First Film", "description": "A fox in Nairobi",
                                               "brief": {"genre": "comedy"}})
    assert created.status_code == 201
    project = created.get_json()["project"]
    assert project["status"] == "draft"

    listed = user.get("/api/projects").get_json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == project["id"]

    renamed = user.patch(f"/api/projects/{project['id']}", json={"title": "Renamed", "status": "in_progress"})
    assert renamed.status_code == 200
    assert renamed.get_json()["project"]["title"] == "Renamed"

    detail = user.get(f"/api/projects/{project['id']}").get_json()
    assert detail["project"]["brief"] == {"genre": "comedy"}
    assert detail["characters"] == [] and detail["scenes"] == []

    assert user.delete(f"/api/projects/{project['id']}").status_code == 204
    assert user.get(f"/api/projects/{project['id']}").status_code == 404


def test_project_validation(make_user):
    user = make_user()
    assert user.post("/api/projects", json={"title": ""}).status_code == 422
    assert user.post("/api/projects", json={"title": "x" * 121}).status_code == 422
    assert user.post("/api/projects", data="not json").status_code == 415
    assert user.post("/api/projects", json={"title": "ok", "owner_id": "x"}).status_code == 422


def test_search_and_filter(make_user):
    user = make_user()
    for title in ("Lion Story", "Ocean Ad", "Lion Sequel"):
        user.post("/api/projects", json={"title": title})
    result = user.get("/api/projects?q=lion").get_json()
    assert result["total"] == 2
    assert user.get("/api/projects?q=%25").get_json()["total"] == 0  # % is matched literally
    assert user.get("/api/projects?status=bogus").status_code == 400


def test_cross_user_project_access_is_blocked(make_user):
    owner, intruder = make_user(), make_user()
    project = owner.post("/api/projects", json={"title": "Secret"}).get_json()["project"]
    pid = project["id"]
    assert intruder.get(f"/api/projects/{pid}").status_code == 404
    assert intruder.patch(f"/api/projects/{pid}", json={"title": "Hacked"}).status_code == 404
    assert intruder.delete(f"/api/projects/{pid}").status_code == 404
    assert intruder.post(f"/api/projects/{pid}/duplicate").status_code == 404
    assert intruder.post(f"/api/projects/{pid}/scenes", json={"title": "x"}).status_code == 404
    assert intruder.post(f"/api/projects/{pid}/characters", json={"name": "x"}).status_code == 404
    assert intruder.get(f"/api/projects/{pid}/assets").status_code == 404
    assert intruder.get(f"/api/projects/{pid}/jobs").status_code == 404
    assert intruder.get("/api/projects").get_json()["total"] == 0
    assert owner.get(f"/api/projects/{pid}").get_json()["project"]["title"] == "Secret"


def test_characters_and_scenes_storyboard(make_user):
    user = make_user()
    pid = user.post("/api/projects", json={"title": "Story"}).get_json()["project"]["id"]
    hero = user.post(f"/api/projects/{pid}/characters", json={
        "name": "Zuri", "description": "Curious fox", "traits": {"color": "orange"}}).get_json()["character"]

    s1 = user.post(f"/api/projects/{pid}/scenes", json={"title": "Opening", "character_ids": [hero["id"]],
                                                       "duration_seconds": 8}).get_json()["scene"]
    s2 = user.post(f"/api/projects/{pid}/scenes", json={"title": "Chase"}).get_json()["scene"]
    s3 = user.post(f"/api/projects/{pid}/scenes", json={"title": "Ending"}).get_json()["scene"]
    assert [s1["position"], s2["position"], s3["position"]] == [0, 1, 2]
    assert s1["character_ids"] == [hero["id"]]

    reordered = user.put(f"/api/projects/{pid}/scenes/order",
                         json={"scene_ids": [s3["id"], s1["id"], s2["id"]]})
    assert reordered.status_code == 200
    assert [s["title"] for s in reordered.get_json()["scenes"]] == ["Ending", "Opening", "Chase"]
    assert user.put(f"/api/projects/{pid}/scenes/order", json={"scene_ids": [s1["id"]]}).status_code == 422

    assert user.delete(f"/api/projects/{pid}/scenes/{s1['id']}").status_code == 204
    scenes = user.get(f"/api/projects/{pid}").get_json()["scenes"]
    assert [(s["title"], s["position"]) for s in scenes] == [("Ending", 0), ("Chase", 1)]

    updated = user.patch(f"/api/projects/{pid}/scenes/{s2['id']}",
                         json={"shot_notes": "Wide shot", "duration_seconds": None})
    assert updated.get_json()["scene"]["shot_notes"] == "Wide shot"


def test_scene_cannot_reference_other_projects_characters(make_user):
    user = make_user()
    a = user.post("/api/projects", json={"title": "A"}).get_json()["project"]["id"]
    b = user.post("/api/projects", json={"title": "B"}).get_json()["project"]["id"]
    char = user.post(f"/api/projects/{a}/characters", json={"name": "Only in A"}).get_json()["character"]
    response = user.post(f"/api/projects/{b}/scenes", json={"title": "x", "character_ids": [char["id"]]})
    assert response.status_code == 422
    assert user.delete(f"/api/projects/{b}/characters/{char['id']}").status_code == 404


def test_duplicate_copies_structure(make_user):
    user = make_user()
    pid = user.post("/api/projects", json={"title": "Original"}).get_json()["project"]["id"]
    char = user.post(f"/api/projects/{pid}/characters", json={"name": "Zuri"}).get_json()["character"]
    user.post(f"/api/projects/{pid}/scenes", json={"title": "One", "character_ids": [char["id"]]})
    copy = user.post(f"/api/projects/{pid}/duplicate").get_json()["project"]
    assert copy["title"] == "Original (copy)"
    detail = user.get(f"/api/projects/{copy['id']}").get_json()
    assert detail["characters"][0]["name"] == "Zuri"
    assert detail["characters"][0]["id"] != char["id"]
    assert detail["scenes"][0]["character_ids"] == [detail["characters"][0]["id"]]


def test_dashboard_shows_only_real_data(make_user):
    user = make_user()
    data = user.get("/api/me/dashboard").get_json()
    assert data["credits"]["balance"] == 0
    assert data["recent_jobs"] == [] and data["recent_projects"] == []
    user.post("/api/projects", json={"title": "P"})
    assert user.get("/api/me/dashboard").get_json()["counts"]["projects"] == 1
