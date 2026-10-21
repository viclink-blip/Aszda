"""Security headers added to every API response."""

from flask import Flask, Response


def register_security_headers(app: Flask) -> None:
    @app.after_request
    def add_headers(response: Response) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # The API only returns JSON and media files, never HTML to render.
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        if not app.config.get("TESTING") and app.config.get("COOKIE_SECURE"):
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store"
        return response
