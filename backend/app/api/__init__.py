from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.api import (
        admin,
        admin_pricing,
        assets,
        auth,
        billing,
        director,
        generation,
        health,
        me,
        openapi,
        projects,
    )

    for blueprint in (health.bp, auth.bp, me.bp, projects.bp, assets.bp, assets.files_bp,
                      generation.bp, director.bp, billing.bp, admin.bp, admin_pricing.bp, openapi.bp):
        app.register_blueprint(blueprint)
