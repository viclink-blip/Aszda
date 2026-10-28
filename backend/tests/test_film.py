"""Automatic films: one request plans the story, makes every scene's image, video and voice,
and joins them into one video. Providers are mocked; the join uses real ffmpeg in its own test."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid

import httpx
import pytest

from app.extensions import db
from app.models import Asset, FilmProduction, GenerationJob
from app.providers.anthropic_text import AnthropicTextAdapter
from app.providers.base import ProviderError
from app.services import credit_service, film_assembly, pricing
from tests.test_ai_providers import PLAN, FakeAnthropic, _image_response, add_prices, price


def idem() -> dict:
    return {"Idempotency-Key": f"film-{uuid.uuid4()}"}


@pytest.fixture()
def film_setup(app, monkeypatch):
    for key, value in {"ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": "k", "AI_IMAGE_PROVIDER": "openai",
                       "AI_VIDEO_PROVIDER": "fake-video", "AI_VIDEO_FALLBACKS": []}.items():
        monkeypatch.setitem(app.config, key, value)
    add_prices({"anthropic:claude-opus-5-5": price(input_tokens=1, output_tokens=5),
                "openai:gpt-image-2.5-sunburst": price(images_medium=8000),
                "openai:gpt-4o-mini-tts": pricing.ModelPrice(credits_per_1000={"characters": 8}, minimum_credits=2),
                "fake-video:fake-motion": price(video_seconds=10_000)})
    fake = FakeAnthropic(json.dumps(PLAN))
    monkeypatch.setattr(AnthropicTextAdapter, "_client", lambda self: fake)

    def fake_post(url, json=None, headers=None, timeout=None):
        if url.endswith("/images/generations"):
            return _image_response()()
        return httpx.Response(200, content=b"ID3voice")
    monkeypatch.setattr(httpx, "post", fake_post)

    joined = []

    def fake_join(segments, out, *, portrait=False):
        joined.append({"segments": segments, "portrait": portrait,
                       "audio": [s.audio.read_bytes() if s.audio else None for s in segments],
                       "video": [s.video.read_bytes() for s in segments]})
        out.write_bytes(b"\x00\x00\x00\x18ftypmp42joined")
        return out, 12.0
    monkeypatch.setattr(film_assembly, "join", fake_join)
    return joined


@pytest.fixture()
def videos_keep_running(monkeypatch):
    """Video jobs are submitted but never polled, so the film stays in production."""
    from app.services import generation_service

    monkeypatch.setattr(generation_service, "_enqueue_poll", lambda job: None)


def new_project(user) -> str:
    return user.post("/api/projects", json={"title": "Fox film"}).get_json()["project"]["id"]


def start(user, pid, headers=None, **body):
    return user.post(f"/api/projects/{pid}/director/films", headers=headers or idem(),
                     json={"idea": "A fox who sells shoes at the market", **body})


def current(user, pid):
    return user.get(f"/api/projects/{pid}/director/films/current").get_json()["film"]


def balance(user) -> int:
    return user.get("/api/me/credits").get_json()["account"]["balance"]


def test_one_request_makes_the_whole_film(app, make_user, film_setup):
    user = make_user(credits=2000)
    pid = new_project(user)
    response = start(user, pid, orientation="portrait")
    assert response.status_code == 201, response.get_json()
    film = current(user, pid)
    assert film["status"] == "completed", film
    assert [s["title"] for s in film["scenes"]] == ["Market", "Night"]
    market, night = film["scenes"]
    assert market["image"]["state"] == market["video"]["state"] == market["voice"]["state"] == "done"
    assert night["voice"]["state"] == "skipped"  # no narration or dialogue in that scene
    assert film["counts"] == {"image": {"done": 2, "total": 2}, "video": {"done": 2, "total": 2},
                              "voice": {"done": 1, "total": 1}}
    # The film is one new video in the project.
    asset = film["film_asset"]
    assert asset["kind"] == "video" and asset["display_name"] == "Fox film - full film"
    assert asset["duration_seconds"] == 12.0 and asset["provider"] == "aszda"
    listed = user.get(f"/api/projects/{pid}/assets?kind=video").get_json()["items"]
    assert asset["id"] in [a["id"] for a in listed]
    # Joined in scene order, portrait, with the Market narration and no voice for Night.
    joined = film_setup[0]
    assert joined["portrait"] is True and joined["audio"] == [b"ID3voice", None]
    # Each video started from its scene's image (the key frame).
    with app.app_context():
        for scene in film["scenes"]:
            video = db.session.get(GenerationJob, uuid.UUID(scene["video"]["job_id"]))
            assert video.input_params["reference_asset_id"] == scene["image"]["asset_id"]
    # The customer paid exactly what the jobs charged; the joining itself is free.
    assert balance(user) == 2000 - film["credits_charged"]
    # The estimate (plan included) is an upper bound: never below what was actually used.
    assert 0 < film["credits_charged"] <= film["estimated_credits"]


def test_the_same_request_twice_starts_one_film(app, make_user, film_setup, videos_keep_running):
    user = make_user(credits=2000)
    pid = new_project(user)
    key = idem()
    first = start(user, pid, headers=key)
    again = start(user, pid, headers=key)
    assert first.status_code == 201 and again.status_code == 200
    assert first.get_json()["film"]["id"] == again.get_json()["film"]["id"]
    other = start(user, pid)
    assert other.status_code == 409 and other.get_json()["error"]["code"] == "film_in_progress"
    assert current(user, pid)["status"] == "producing"


def test_film_waits_for_credits_then_continues(app, make_user, film_setup):
    user = make_user(credits=100)  # enough for the plan only
    pid = new_project(user)
    film = start(user, pid).get_json()["film"]
    film = current(user, pid)
    assert film["status"] == "waiting_for_credits"
    assert film["error"]["code"] == "insufficient_credits" and "credits" in film["error"]["message"]
    assert all(s["image"]["state"] == "waiting" for s in film["scenes"])  # nothing was started
    with app.app_context():
        credit_service.grant(uuid.UUID(str(user.id)), 2000, reference=f"t:{uuid.uuid4()}", reason="top up",
                             actor_id=None)
        db.session.commit()
    resumed = user.post(f"/api/projects/{pid}/director/films/{film['id']}/continue")
    assert resumed.status_code == 200
    assert current(user, pid)["status"] == "completed"
    # Continue only applies to a waiting film.
    assert user.post(f"/api/projects/{pid}/director/films/{film['id']}/continue").status_code == 409


def test_a_failed_plan_fails_the_film_and_refunds(app, make_user, film_setup, monkeypatch):
    def broken(self):
        raise ProviderError("Anthropic is down.", code="provider_unavailable")
    monkeypatch.setattr(AnthropicTextAdapter, "_client", broken)
    user = make_user(credits=500)
    pid = new_project(user)
    start(user, pid)
    film = current(user, pid)
    assert film["status"] == "failed" and film["error"]["code"] == "plan_failed"
    assert balance(user) == 500


def test_a_failed_join_keeps_the_clips(app, make_user, film_setup, monkeypatch):
    def broken(segments, out, *, portrait=False):
        raise film_assembly.AssemblyError("ffmpeg failed")
    monkeypatch.setattr(film_assembly, "join", broken)
    user = make_user(credits=2000)
    pid = new_project(user)
    start(user, pid)
    film = current(user, pid)
    assert film["status"] == "failed" and film["error"]["code"] == "assembly_failed"
    assert film["counts"]["video"]["done"] == 2 and film["film_asset"] is None


def test_cancel_stops_new_steps(app, make_user, film_setup, videos_keep_running):
    user = make_user(credits=2000)
    pid = new_project(user)
    film = start(user, pid).get_json()["film"]
    cancelled = user.post(f"/api/projects/{pid}/director/films/{film['id']}/cancel")
    assert cancelled.status_code == 200 and cancelled.get_json()["film"]["status"] == "cancelled"
    assert user.post(f"/api/projects/{pid}/director/films/{film['id']}/cancel").status_code == 409
    # A new film may start once the old one is stopped.
    assert start(user, pid).status_code == 201


def test_films_are_private(app, make_user, film_setup):
    owner, stranger = make_user(credits=2000), make_user(credits=2000)
    pid = new_project(owner)
    film = start(owner, pid).get_json()["film"]
    assert stranger.get(f"/api/projects/{pid}/director/films/current").status_code == 404
    assert stranger.post(f"/api/projects/{pid}/director/films/{film['id']}/cancel").status_code == 404
    other_pid = new_project(stranger)
    assert stranger.post(f"/api/projects/{other_pid}/director/films/{film['id']}/cancel").status_code == 404


def test_beat_moves_a_film_on_when_a_wake_up_was_missed(app, make_user, film_setup, monkeypatch):
    from app.services import film_service, generation_service

    monkeypatch.setattr(generation_service, "_enqueue_poll", lambda job: None)
    user = make_user(credits=2000)
    pid = new_project(user)
    start(user, pid)
    assert current(user, pid)["status"] == "producing"
    # The videos finish without the film being told (a lost wake-up); the beat task catches up.
    monkeypatch.setattr(film_service, "job_finished", lambda job: None)
    with app.app_context():
        for _ in range(3):
            for job in db.session.query(GenerationJob).filter(GenerationJob.kind == "video").all():
                generation_service.poll_job(job.id)
        assert current(user, pid)["status"] == "producing"
        assert film_service.advance_active() == 1
    assert current(user, pid)["status"] == "completed"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_join_with_real_ffmpeg(tmp_path):
    def make(args, name):
        subprocess.run(["ffmpeg", "-v", "error", *args, str(tmp_path / name)], check=True)
        return tmp_path / name

    silent = make(["-f", "lavfi", "-i", "testsrc=size=1280x720:rate=24", "-t", "2", "-pix_fmt", "yuv420p"], "a.mp4")
    square = make(["-f", "lavfi", "-i", "testsrc2=size=960x960:rate=30", "-f", "lavfi", "-i", "sine=f=440",
                   "-t", "3", "-pix_fmt", "yuv420p", "-shortest"], "b.mp4")
    voice = make(["-f", "lavfi", "-i", "sine=f=220", "-t", "3.5"], "voice.mp3")
    out, length = film_assembly.join([film_assembly.Segment(silent, voice), film_assembly.Segment(square)],
                                     tmp_path / "film.mp4", portrait=True)
    # The 2 s clip is held on its last frame until the 3.5 s voice ends; then the 3 s clip.
    assert length == pytest.approx(6.5, abs=0.1)
    probe = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
         "-of", "json", str(out)], capture_output=True, text=True, check=True).stdout)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (720, 1280)
    assert any(s["codec_type"] == "audio" for s in probe["streams"])
    assert float(probe["format"]["duration"]) == pytest.approx(6.5, abs=0.15)


def test_join_refuses_an_empty_film(tmp_path):
    with pytest.raises(film_assembly.AssemblyError):
        film_assembly.join([], tmp_path / "film.mp4")


def test_assets_of_a_film_are_deleted_with_the_project(app, make_user, film_setup):
    user = make_user(credits=2000)
    pid = new_project(user)
    start(user, pid)
    assert user.delete(f"/api/projects/{pid}").status_code in (200, 204)
    with app.app_context():
        assert db.session.query(FilmProduction).count() == 0
        assert db.session.query(Asset).filter(Asset.project_id == uuid.UUID(pid)).count() == 0
