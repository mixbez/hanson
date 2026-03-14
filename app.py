#!/usr/bin/env python3

"""
Рынок Предсказаний — Prediction Market for Vas3k Club
Based on Hanson LMSR prediction market engine.
"""

import os
import sys

from flask import Flask
from authlib.integrations.flask_client import OAuth

from hanson.http import Response
from hanson.models.config import Config
from hanson.routes import assets as route_assets
from hanson.routes import auth as route_auth
from hanson.routes import admin as route_admin
from hanson.routes import index as route_index
from hanson.routes import market as route_market
from hanson.routes import session as route_session
from hanson.routes import user as route_user
from hanson.util.session import NotLoggedInError


def create_app(config: Config) -> Flask:
    flask_app = Flask(import_name="hanson")
    flask_app.config["hanson_config"] = config

    # Flask session secret (used by authlib state/nonce storage)
    flask_app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")

    # ── Authlib OIDC client ────────────────────────────────────────────────────
    oauth = OAuth(flask_app)
    oauth.register(
        name="vas3k",
        client_id=os.environ["OIDC_CLIENT_ID"],
        client_secret=os.environ["OIDC_CLIENT_SECRET"],
        # vas3k.club OpenID Connect well-known endpoint
        server_metadata_url=(
            os.environ.get("VAS3K_BASE_URL", "https://vas3k.club")
            + "/.well-known/openid-configuration"
        ),
        client_kwargs={
            "scope": "openid",
            "token_endpoint_auth_method": "client_secret_basic",
        },
    )

    # ── Blueprints ────────────────────────────────────────────────────────────
    flask_app.register_blueprint(route_assets.app)
    flask_app.register_blueprint(route_auth.app)
    flask_app.register_blueprint(route_admin.app)
    flask_app.register_blueprint(route_index.app)
    flask_app.register_blueprint(route_market.app)
    flask_app.register_blueprint(route_session.app)
    flask_app.register_blueprint(route_user.app)

    @flask_app.errorhandler(NotLoggedInError)
    def handle_not_logged_in(_: NotLoggedInError) -> Response:
        return Response.redirect_see_other("/login")

    return flask_app


def _load_config() -> Config:
    config_file = os.environ.get("HANSON_CONFIG", "config.toml")
    return Config.load_from_toml_file(config_file)


def main() -> None:
    """
    Run the prediction market in production mode via Waitress WSGI server.

    Usage: app.py [config.toml]

    Configuration can also be provided through environment variables:
      DATABASE_URL      - PostgreSQL connection URL (alternative to config.toml)
      OIDC_CLIENT_ID    - OAuth2 client ID registered on vas3k.club
      OIDC_CLIENT_SECRET - OAuth2 client secret
      FLASK_SECRET_KEY  - Flask session secret key
      VAS3K_BASE_URL    - Base URL of vas3k.club (default: https://vas3k.club)
    """
    import waitress  # type: ignore
    import textwrap

    config = _load_config()

    flask_app = create_app(config)

    print("Starting server ...")
    waitress.serve(flask_app, host=config.server.host, port=config.server.port)


# ── Vercel / WSGI entry point ─────────────────────────────────────────────────
# When imported (not run directly), expose `app` for WSGI servers and Vercel.
config = _load_config()
app = create_app(config)


if __name__ == "__main__":
    main()
