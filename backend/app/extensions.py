"""Flask extension instances, created once and bound to the app in create_app()."""

from flask_limiter import Limiter
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData

# A naming convention gives every constraint a predictable name, which keeps
# Alembic migrations stable across databases.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=NAMING_CONVENTION))
migrate = Migrate()


def _rate_limit_key() -> str:
    # Authenticated requests are limited per user; anonymous ones per client IP.
    from flask import g, request

    user = getattr(g, "current_user", None)
    if user is not None:
        return f"user:{user.id}"
    return f"ip:{request.remote_addr or 'unknown'}"


limiter = Limiter(key_func=_rate_limit_key)
