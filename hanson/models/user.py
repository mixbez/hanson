from __future__ import annotations

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Iterable, List, NamedTuple, Optional, Tuple

from hanson.database import Transaction
from hanson.models.currency import Points

REGISTRATION_BONUS = Points(Decimal("10000.00"))
DAILY_BONUS = Points(Decimal("100.00"))

# Roles from vas3k.club that grant moderation privileges
CLUB_MOD_ROLES = {"moderator", "god", "curator"}


class User(NamedTuple):
    id: int
    username: str
    full_name: str
    created_at: datetime
    club_user_id: Optional[str]
    club_roles: List[str]
    last_daily_bonus_at: Optional[datetime]
    is_market_admin: bool

    # ── Role helpers ──────────────────────────────────────────────────────────

    def is_club_moderator(self) -> bool:
        """True if the user has moderator/god/curator role in vas3k.club."""
        return bool(set(self.club_roles) & CLUB_MOD_ROLES)

    def can_delete_market(self) -> bool:
        return self.is_market_admin or self.is_club_moderator()

    def can_resolve_market(self) -> bool:
        return self.is_market_admin or self.is_club_moderator()

    def can_gift_tokens(self) -> bool:
        return self.is_market_admin

    # ── Daily bonus logic ─────────────────────────────────────────────────────

    def needs_daily_bonus(self) -> bool:
        """True if the user hasn't received their daily bonus yet today (UTC)."""
        if self.last_daily_bonus_at is None:
            return True
        today = datetime.now(timezone.utc).date()
        last = self.last_daily_bonus_at.date()
        return last < today

    # ── Database operations ───────────────────────────────────────────────────

    @staticmethod
    def _from_row(row: tuple) -> User:
        (
            user_id,
            current_username,
            current_full_name,
            created_at,
            club_user_id,
            club_roles,
            last_daily_bonus_at,
            is_market_admin,
        ) = row
        return User(
            id=user_id,
            username=current_username or "",
            full_name=current_full_name or "",
            created_at=created_at,
            club_user_id=club_user_id,
            club_roles=club_roles or [],
            last_daily_bonus_at=last_daily_bonus_at,
            is_market_admin=bool(is_market_admin),
        )

    @staticmethod
    def _select_fields() -> str:
        return """
            id,
            current_username,
            current_full_name,
            created_at,
            club_user_id,
            club_roles,
            last_daily_bonus_at,
            is_market_admin
        """

    @staticmethod
    def get_by_id(tx: Transaction, user_id: int) -> Optional[User]:
        result = tx.execute_fetch_optional(
            f"SELECT {User._select_fields()} FROM users_ext WHERE id = %s;",
            (user_id,),
        )
        return User._from_row(result) if result is not None else None

    @staticmethod
    def get_by_username(tx: Transaction, username: str) -> Optional[User]:
        result = tx.execute_fetch_optional(
            """
            SELECT user_id
            FROM user_usernames
            WHERE username = %s
            """,
            (username,),
        )
        if result is None:
            return None
        return User.get_by_id(tx, result[0])

    @staticmethod
    def create(tx: Transaction, username: str, full_name: str) -> User:
        """Create a local user without a club account (for CLI/tests)."""
        user_id, created_at = tx.execute_fetch_one(
            "INSERT INTO users DEFAULT VALUES RETURNING id, created_at;",
        )
        tx.execute(
            "INSERT INTO user_usernames (user_id, username) VALUES (%s, %s);",
            (user_id, username),
        )
        tx.execute(
            "INSERT INTO user_full_names (user_id, full_name) VALUES (%s, %s);",
            (user_id, full_name),
        )
        user = User.get_by_id(tx, user_id)
        assert user is not None
        return user

    @staticmethod
    def get_by_club_user_id(tx: Transaction, club_user_id: str) -> Optional[User]:
        result = tx.execute_fetch_optional(
            f"SELECT {User._select_fields()} FROM users_ext WHERE club_user_id = %s;",
            (club_user_id,),
        )
        return User._from_row(result) if result is not None else None

    @staticmethod
    def get_or_create_from_club(
        tx: Transaction,
        club_user_id: str,
        username: str,
        full_name: str,
        club_roles: List[str],
    ) -> Tuple[User, bool]:
        """
        Find an existing user by their vas3k.club slug, or create one.
        Returns (user, is_new).
        """
        existing = User.get_by_club_user_id(tx, club_user_id)
        if existing is not None:
            # Update roles and name in case they changed
            tx.execute(
                """
                UPDATE users
                SET club_roles = %s
                WHERE id = %s
                """,
                (club_roles, existing.id),
            )
            # Update full name if changed
            current_name = existing.full_name
            if current_name != full_name and full_name:
                tx.execute(
                    "INSERT INTO user_full_names (user_id, full_name) VALUES (%s, %s);",
                    (existing.id, full_name),
                )
            refreshed = User.get_by_id(tx, existing.id)
            return refreshed, False

        # Create new user
        user_id, created_at = tx.execute_fetch_one(
            """
            INSERT INTO users (club_user_id, club_roles)
            VALUES (%s, %s)
            RETURNING id, created_at;
            """,
            (club_user_id, club_roles),
        )
        # username must be unique; append numeric suffix if needed
        safe_username = _make_safe_username(username)
        tx.execute(
            "INSERT INTO user_usernames (user_id, username) VALUES (%s, %s);",
            (user_id, safe_username),
        )
        if full_name:
            tx.execute(
                "INSERT INTO user_full_names (user_id, full_name) VALUES (%s, %s);",
                (user_id, full_name),
            )
        user = User(
            id=user_id,
            username=safe_username,
            full_name=full_name or safe_username,
            created_at=created_at,
            club_user_id=club_user_id,
            club_roles=club_roles,
            last_daily_bonus_at=None,
            is_market_admin=False,
        )
        return user, True

    def mark_daily_bonus(self, tx: Transaction) -> None:
        tx.execute(
            "UPDATE users SET last_daily_bonus_at = now() WHERE id = %s;",
            (self.id,),
        )

    @staticmethod
    def list_all(tx: Transaction) -> Iterable[User]:
        for row in tx.execute_fetch_all(
            f"""
            SELECT {User._select_fields()}
            FROM users_ext
            ORDER BY created_at ASC;
            """
        ):
            yield User._from_row(row)

    @staticmethod
    def grant_market_admin(tx: Transaction, user_id: int, granted_by_id: int) -> None:
        tx.execute(
            """
            INSERT INTO market_admins (user_id, granted_by)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING;
            """,
            (user_id, granted_by_id),
        )

    @staticmethod
    def revoke_market_admin(tx: Transaction, user_id: int) -> None:
        tx.execute(
            "DELETE FROM market_admins WHERE user_id = %s;",
            (user_id,),
        )


def _make_safe_username(raw: str) -> str:
    """Convert a vas3k.club slug into a valid local username (lowercase ascii)."""
    import re
    # slugs from vas3k.club are already slug-safe but may contain digits/hyphens
    cleaned = re.sub(r"[^a-z0-9]", "", raw.lower())
    return cleaned or "user"
