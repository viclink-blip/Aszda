"""The signed-in user's own account, credits and dashboard summary."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, make_response
from sqlalchemy import func, select

from app.api.auth import _clear_cookie
from app.api.common import doc, page, pagination, parse_body
from app.extensions import db
from app.models import ACTIVE_STATUSES, Asset, CreditTransaction, GenerationJob, Project
from app.schemas.requests import ChangePasswordIn, DeleteAccountIn, ProfileUpdateIn
from app.schemas.serializers import (
    asset_out,
    credit_account_out,
    credit_tx_out,
    job_out,
    project_out,
    user_out,
)
from app.security.auth import current_user, login_required
from app.services import auth_service, credit_service, project_service

bp = Blueprint("me", __name__, url_prefix="/api/me")


@bp.get("")
@doc("Get my account", tags=["Account"])
@login_required
def get_me():
    return jsonify({"user": user_out(current_user())})


@bp.patch("")
@doc("Update my profile", tags=["Account"], body=ProfileUpdateIn)
@login_required
def update_me():
    data = parse_body(ProfileUpdateIn).model_dump(exclude_unset=True)
    user = current_user()
    for key, value in data.items():
        if key == "display_name" and value is None:
            continue
        setattr(user.profile, key, value.upper() if key == "country" and value else value)
    db.session.commit()
    return jsonify({"user": user_out(user)})


@bp.post("/password")
@doc("Change my password (signs out other devices)", tags=["Account"], body=ChangePasswordIn)
@login_required
def change_password():
    data = parse_body(ChangePasswordIn)
    auth_service.change_password(current_user(), data.current_password, data.new_password,
                                 keep_session_id=g.current_session.id)
    return "", 204


@bp.delete("")
@doc("Permanently delete my account and all my data", tags=["Account"], body=DeleteAccountIn)
@login_required
def delete_me():
    data = parse_body(DeleteAccountIn)
    auth_service.delete_account(current_user(), data.password)
    return _clear_cookie(make_response("", 204))


@bp.get("/credits")
@doc("My credit balance and recent ledger entries", tags=["Credits"])
@login_required
def my_credits():
    user = current_user()
    account = credit_service.get_account(user.id)
    db.session.commit()
    limit, offset = pagination()
    query = select(CreditTransaction).where(CreditTransaction.account_id == account.id)
    total = db.session.scalar(select(func.count()).select_from(query.subquery()))
    txs = db.session.scalars(query.order_by(CreditTransaction.created_at.desc())
                             .limit(limit).offset(offset)).all()
    return jsonify({"account": credit_account_out(account),
                    "transactions": page([credit_tx_out(t) for t in txs], total, limit, offset)})


@bp.get("/dashboard")
@doc("Everything the dashboard needs in one request", tags=["Account"])
@login_required
def dashboard():
    user = current_user()
    account = credit_service.get_account(user.id)
    db.session.commit()
    projects = db.session.scalars(select(Project).where(Project.owner_id == user.id)
                                  .order_by(Project.updated_at.desc()).limit(6)).all()
    stats = project_service.project_stats([p.id for p in projects])
    jobs = db.session.scalars(select(GenerationJob).where(GenerationJob.user_id == user.id)
                              .order_by(GenerationJob.created_at.desc()).limit(8)).all()
    project_count = db.session.scalar(select(func.count()).select_from(Project)
                                      .where(Project.owner_id == user.id))
    asset_count = db.session.scalar(select(func.count()).select_from(Asset).where(Asset.owner_id == user.id))
    active_jobs = db.session.scalar(select(func.count()).select_from(GenerationJob).where(
        GenerationJob.user_id == user.id, GenerationJob.status.in_(ACTIVE_STATUSES)))
    recent_assets = db.session.scalars(select(Asset).where(Asset.owner_id == user.id)
                                       .order_by(Asset.created_at.desc()).limit(6)).all()
    return jsonify({
        "user": user_out(user),
        "credits": credit_account_out(account),
        "counts": {"projects": project_count, "assets": asset_count, "active_jobs": active_jobs},
        "recent_projects": [project_out(p, stats.get(p.id)) for p in projects],
        "recent_jobs": [job_out(j) for j in jobs],
        "recent_assets": [asset_out(a) for a in recent_assets],
    })
