from flask import Flask


def register_blueprints(app: Flask) -> None:
    from app.api import admin, assets, auth, generation, health, me, openapi, projects

    for blueprint in (health.bp, auth.bp, me.bp, projects.bp, assets.bp, assets.files_bp,
                      generation.bp, admin.bp, openapi.bp):
        app.register_blueprint(blueprint)
