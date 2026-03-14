"""
Admin panel for market_admin users:
  - Gift extra tokens to any user
  - Grant / revoke market_admin role
"""
from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, render_template, request

import hanson.models.transaction as transaction
from hanson.database import Transaction
from hanson.http import Response
from hanson.models.currency import Points
from hanson.models.user import User
from hanson.util.decorators import with_tx
from hanson.util.session import get_session_user

app = Blueprint(name="admin", import_name=__name__)


@app.get("/admin")
@with_tx
def route_get_admin(tx: Transaction) -> Response:
    session_user = get_session_user(tx)

    if not session_user.user.can_gift_tokens():
        return Response.forbidden("Только market_admin может заходить в панель администратора.")

    users = list(User.list_all(tx))
    return Response.ok_html(
        render_template(
            "admin.html",
            session_user=session_user,
            users=users,
        )
    )


@app.post("/admin/gift_tokens")
@with_tx
def route_post_gift_tokens(tx: Transaction) -> Response:
    session_user = get_session_user(tx)

    if not session_user.user.can_gift_tokens():
        return Response.forbidden("Только market_admin может выдавать жетоны.")

    recipient_id_str = request.form.get("user_id", "")
    amount_str = request.form.get("amount", "")

    if not recipient_id_str.isdigit():
        return Response.bad_request("Неверный user_id.")

    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError
    except Exception:
        return Response.bad_request("Сумма должна быть положительным числом.")

    recipient = User.get_by_id(tx, int(recipient_id_str))
    if recipient is None:
        return Response.not_found("Пользователь не найден.")

    transaction.create_transaction_income(tx, recipient.id, Points(amount))
    tx.commit()

    return Response.redirect_see_other("/admin")


@app.post("/admin/grant_market_admin")
@with_tx
def route_post_grant_market_admin(tx: Transaction) -> Response:
    session_user = get_session_user(tx)

    if not session_user.user.can_gift_tokens():
        return Response.forbidden("Только market_admin может назначать администраторов рынка.")

    user_id_str = request.form.get("user_id", "")
    if not user_id_str.isdigit():
        return Response.bad_request("Неверный user_id.")

    User.grant_market_admin(tx, int(user_id_str), session_user.user.id)
    tx.commit()

    return Response.redirect_see_other("/admin")


@app.post("/admin/revoke_market_admin")
@with_tx
def route_post_revoke_market_admin(tx: Transaction) -> Response:
    session_user = get_session_user(tx)

    if not session_user.user.can_gift_tokens():
        return Response.forbidden("Только market_admin может отзывать права администратора рынка.")

    user_id_str = request.form.get("user_id", "")
    if not user_id_str.isdigit():
        return Response.bad_request("Неверный user_id.")

    User.revoke_market_admin(tx, int(user_id_str))
    tx.commit()

    return Response.redirect_see_other("/admin")
