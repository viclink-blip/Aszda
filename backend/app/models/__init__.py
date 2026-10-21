"""All database models. Importing this package registers them with SQLAlchemy."""

from app.models.asset import Asset, AssetKind, AssetSource
from app.models.audit import AuditEvent
from app.models.credits import CreditAccount, CreditTransaction, CreditTxType
from app.models.generation import (
    ACTIVE_STATUSES,
    FINAL_STATUSES,
    GenerationJob,
    GenerationKind,
    JobStatus,
)
from app.models.project import Character, Project, ProjectStatus, Scene, scene_characters
from app.models.user import (
    AuthSession,
    RefreshToken,
    Role,
    TokenPurpose,
    User,
    UserProfile,
    UserToken,
)

__all__ = [
    "ACTIVE_STATUSES", "FINAL_STATUSES", "Asset", "AssetKind", "AssetSource", "AuditEvent",
    "AuthSession", "Character", "CreditAccount", "CreditTransaction", "CreditTxType",
    "GenerationJob", "GenerationKind", "JobStatus", "Project", "ProjectStatus", "RefreshToken",
    "Role", "Scene", "TokenPurpose", "User", "UserProfile", "UserToken", "scene_characters",
]
