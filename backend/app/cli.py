"""Command-line tools: `flask --app wsgi aszda <command>`.

  create-admin      Create an administrator (asks for the password; no default exists)
  grant-credits     Give credits to a user, recorded in the ledger and the audit log
  cleanup-storage   Delete stored files that no asset row points to any more
  check-pricing     Validate the pricing file and list priced models
"""

from __future__ import annotations

import uuid

import click
from flask import Flask
from sqlalchemy import select

from app.extensions import db
from app.models import Asset, Role, User, UserProfile
from app.security.passwords import hash_password, password_problems
from app.services import audit, credit_service


def register_cli(app: Flask) -> None:
    group = click.Group("aszda", help="ASZDA administration commands.")

    @group.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", "display_name", prompt="Display name")
    @click.password_option()
    def create_admin(email: str, display_name: str, password: str) -> None:
        email = email.strip().lower()
        problems = password_problems(password, email)
        if problems:
            raise click.ClickException(" ".join(problems))
        user = db.session.scalar(select(User).where(User.email == email))
        if user is not None:
            user.role = Role.ADMIN
            click.echo(f"Existing user {email} promoted to admin.")
        else:
            user = User(email=email, password_hash=hash_password(password), role=Role.ADMIN)
            user.profile = UserProfile(display_name=display_name.strip()[:80] or "Admin")
            from datetime import UTC, datetime

            user.email_verified_at = datetime.now(UTC)
            db.session.add(user)
            db.session.flush()
            credit_service.ensure_account(user.id)
            click.echo(f"Admin {email} created.")
        audit.record("cli.admin_created", target_type="user", target_id=user.id)
        db.session.commit()

    @group.command("grant-credits")
    @click.argument("email")
    @click.argument("amount", type=int)
    @click.option("--reason", required=True)
    def grant_credits(email: str, amount: int, reason: str) -> None:
        user = db.session.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            raise click.ClickException("No user with that email.")
        if amount <= 0:
            raise click.ClickException("Amount must be positive.")
        tx = credit_service.grant(user.id, amount, reference=f"cli:{uuid.uuid4()}", reason=reason,
                                  actor_id=None)
        audit.record("cli.credits_granted", target_type="user", target_id=user.id, amount=amount,
                     reason=reason)
        db.session.commit()
        click.echo(f"Granted {amount} credits to {email}. New balance: {tx.balance_after}.")

    @group.command("cleanup-storage")
    @click.option("--dry-run/--delete", default=True, help="Only list orphaned files (default).")
    def cleanup_storage(dry_run: bool) -> None:
        from app.storage.backends import LocalStorage, get_storage

        storage = get_storage()
        if not isinstance(storage, LocalStorage):
            raise click.ClickException("Use a bucket lifecycle rule for S3; this command handles local storage.")
        known = set(db.session.scalars(select(Asset.storage_key)))
        orphans = []
        for path in storage.root.rglob("*"):
            if path.is_file():
                key = path.relative_to(storage.root).as_posix()
                if key not in known:
                    orphans.append(key)
        for key in orphans:
            click.echo(("would delete " if dry_run else "deleting ") + key)
            if not dry_run:
                (storage.root / key).unlink(missing_ok=True)
        click.echo(f"{len(orphans)} orphaned file(s).")

    @group.command("check-pricing")
    def check_pricing() -> None:
        from flask import current_app

        from app.providers import registry
        from app.services import pricing

        click.echo(f"Pricing file: {current_app.config['PRICING_FILE'] or '(none — nothing is priced)'}")
        for adapter in registry.all_adapters():
            for spec in adapter.model_specs():
                price = pricing.price_for(adapter.name, spec.id)
                status = f"{price.credits_per_1000} per 1000, min {price.minimum_credits}" if price else "NOT PRICED"
                key = "key set" if adapter.is_configured() else f"missing {adapter.credential_env}"
                click.echo(f"{adapter.name}:{spec.id:<22} {status:<55} [{key}]")

    app.cli.add_command(group)
