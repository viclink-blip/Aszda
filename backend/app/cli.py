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

    @group.command("paystack-check")
    @click.option("--try-usd", is_flag=True,
                  help="Ask Paystack to start (not charge) a $2.00 USD test transaction to see if USD is enabled.")
    @click.option("--allow-live", is_flag=True, help="Allow --try-usd with a live key (creates an unpaid transaction).")
    def paystack_check(try_usd: bool, allow_live: bool) -> None:
        """Check the Paystack set-up: key, USD switch, plan codes, and optionally USD support."""
        from flask import current_app

        from app.billing import paystack
        from app.billing.catalog import get_catalog
        from app.services.payment_service import checkout_status

        mode = paystack.key_mode()
        click.echo(f"Secret key: {'not set' if mode is None else mode + ' key'}")
        click.echo(f"ASZDA_PAYSTACK_USD_ENABLED: {current_app.config['PAYSTACK_USD_ENABLED']}")
        status = checkout_status()
        click.echo(f"Checkout: {'ENABLED' if status['enabled'] else 'disabled (' + status['reason'] + ')'}")
        if mode is None:
            return
        for plan in get_catalog().plans:
            if plan.is_free:
                continue
            if not plan.paystack_plan_code:
                click.echo(f"  plan {plan.code}: no paystack_plan_code configured")
                continue
            try:
                remote = paystack.fetch_plan(plan.paystack_plan_code)
            except paystack.PaystackError as exc:
                click.echo(f"  plan {plan.code}: {plan.paystack_plan_code} could not be fetched ({exc.message})")
                continue
            ok = (remote.get("amount") == plan.price_usd_cents and str(remote.get("currency")).upper() == "USD"
                  and remote.get("interval") == "monthly")
            click.echo(f"  plan {plan.code}: {plan.paystack_plan_code} amount={remote.get('amount')} "
                       f"currency={remote.get('currency')} interval={remote.get('interval')} -> "
                       f"{'MATCHES catalog' if ok else 'DOES NOT MATCH catalog'}")
        if try_usd:
            if mode != "test" and not allow_live:
                raise click.ClickException("--try-usd uses a test key by default; add --allow-live to use a live key.")
            try:
                data = paystack.initialize_transaction(
                    email="usd-check@aszda.invalid", amount_minor=200, currency="USD",
                    reference=f"aszda-usdcheck-{uuid.uuid4().hex[:12]}",
                    callback_url=f"{current_app.config['FRONTEND_URL']}/app/billing/complete",
                    metadata={"purpose": "ASZDA USD capability check; do not pay"})
                click.echo("USD check: Paystack ACCEPTED a USD transaction for this key "
                           f"(checkout link created, nothing charged): {data.get('authorization_url')}")
                click.echo("Next: confirm USD settlement in the Paystack dashboard, then set "
                           "ASZDA_PAYSTACK_USD_ENABLED=true (docs/BILLING.md).")
            except paystack.PaystackError as exc:
                click.echo(f"USD check: Paystack REFUSED a USD transaction: {exc.message}")
                click.echo("Keep ASZDA_PAYSTACK_USD_ENABLED=false and ask Paystack to enable USD.")

    @group.command("pricing-apply")
    @click.argument("path", type=click.Path(exists=True, dir_okay=False))
    @click.option("--yes", is_flag=True, help="Apply. Without it, only show what would change.")
    def pricing_apply(path: str, yes: bool) -> None:
        """Load generation credit costs and plan/package credits from a JSON file into the admin
        settings (see backend/pricing.approved.json). USD prices are never changed by this."""
        import json

        from app.services.pricing_settings import apply_pricing_document

        with open(path, encoding="utf-8") as fh:
            document = json.load(fh)
        try:
            changes = apply_pricing_document(document, actor_id=None, commit=yes)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc
        for line in changes:
            click.echo(line)
        click.echo("Applied." if yes else "Dry run only: nothing changed. Re-run with --yes to apply.")

    @group.command("reap-stuck-jobs")
    def reap_stuck_jobs() -> None:
        """Fail and refund generation jobs whose worker or queue message was lost."""
        from app.services.generation_service import reap_stuck_jobs as reap

        click.echo(reap())

    @group.command("expire-subscriptions")
    def expire_subscriptions() -> None:
        """End cancelled plans whose paid period is over (run daily)."""
        from app.services.payment_service import expire_overdue_subscriptions

        click.echo(f"{expire_overdue_subscriptions()} plan(s) ended.")

    app.cli.add_command(group)
