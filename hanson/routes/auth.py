"""
OIDC-based authentication via vas3k.club.

Flow:
  GET /login           → redirect to vas3k.club authorize endpoint
  GET /auth/callback   → exchange code for token, upsert local user, start session
  GET/POST /logout     → clear session cookie
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from decimal import Decimal

from flask import Blueprint, redirect, request, session, url_for, render_template

from hanson.database import Transaction
from hanson.http import Response
from hanson.models.currency import Points
from hanson.models.session import Session
from hanson.models.transaction import create_transaction_income
from hanson.models.user import DAILY_BONUS, REGISTRATION_BONUS, User
from hanson.util.decorators import with_tx

log = logging.getLogger(__name__)
app = Blueprint(name="auth", import_name=__name__)


def _get_oauth_client():
    """Return the configured authlib OAuth client for vas3k.club."""
    from flask import current_app
    oauth = current_app.extensions.get("authlib.integrations.flask_client")
    return oauth.vas3k


# ── Login ─────────────────────────────────────────────────────────────────────

@app.get("/login")
def route_get_login() -> Response:
    redirect_uri = url_for("auth.route_auth_callback", _external=True)
    return _get_oauth_client().authorize_redirect(redirect_uri)


# ── Callback ──────────────────────────────────────────────────────────────────

@app.get("/auth/callback")
@with_tx
def route_auth_callback(tx: Transaction) -> Response:
    try:
        token = _get_oauth_client().authorize_access_token()
    except Exception as exc:
        log.error("OIDC token exchange failed: %s", exc)
        return Response.redirect_see_other("/login")

    userinfo = token.get("userinfo") or {}

    # vas3k.club uses the user slug as `sub`
    club_user_id: str = userinfo.get("sub") or ""
    full_name: str = userinfo.get("name") or club_user_id
    username: str = club_user_id  # slug is already username-safe
    club_roles: list = userinfo.get("roles") or []
    moderation_status: str = userinfo.get("moderation_status") or ""

    if not club_user_id:
        log.error("OIDC userinfo missing 'sub' field: %s", userinfo)
        return Response.redirect_see_other("/login")

    # Only allow approved club members
    if moderation_status and moderation_status != "approved":
        return Response.forbidden("Только одобренные участники клуба могут использовать рынок предсказаний.")

    user, is_new = User.get_or_create_from_club(
        tx,
        club_user_id=club_user_id,
        username=username,
        full_name=full_name,
        club_roles=club_roles,
    )

    # Grant registration bonus to new users
    if is_new:
        create_transaction_income(tx, user.id, REGISTRATION_BONUS)
        log.info("New user %s — granted %s registration tokens", club_user_id, REGISTRATION_BONUS)

    # Refresh user object after potential upsert
    user = User.get_by_id(tx, user.id)

    # Grant daily bonus on first login of the day
    if user.needs_daily_bonus():
        create_transaction_income(tx, user.id, DAILY_BONUS)
        user.mark_daily_bonus(tx)
        log.info("User %s — granted %s daily tokens", club_user_id, DAILY_BONUS)

    local_session = Session.create(tx, user.id)
    tx.commit()

    response = Response.redirect_see_other("/")
    response.add_set_cookie_header("session", str(local_session.token), local_session.expires_at)
    return response


# ── Logout ────────────────────────────────────────────────────────────────────

@app.get("/logout")
def route_get_logout() -> Response:
    return Response.ok_html(render_template("logout.html"))


@app.post("/logout")
def route_post_logout() -> Response:
    date_in_past = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    response = Response.redirect_see_other("/")
    response.add_set_cookie_header("session", "", date_in_past)
    return response
