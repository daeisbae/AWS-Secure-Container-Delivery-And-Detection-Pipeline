"""Deliberately vulnerable shop data and authentication code for the lab."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from typing import Protocol

from authlib.jose import jwt
from sqlalchemy import (
    Column,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    create_engine,
    select,
    text,
)
from sqlalchemy.engine import Connection
from sqlalchemy.pool import StaticPool


class Credentials(Protocol):
    username: str
    password: str


@dataclass(frozen=True)
class UserRecord:
    id: int
    username: str


metadata = MetaData()
products_table = Table(
    "products",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("price_cents", Integer, nullable=False),
)
users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("username", String, nullable=False, unique=True),
    Column("password_salt", LargeBinary, nullable=False),
    Column("password_hash", LargeBinary, nullable=False),
)

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
metadata.create_all(engine)

_token_key = secrets.token_bytes(32)


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)


_seed_salt = secrets.token_bytes(16)
_seed_password = os.environ.get("SHOP_DEMO_PASSWORD") or secrets.token_urlsafe(48)
with engine.begin() as seed_connection:
    seed_connection.execute(
        products_table.insert(),
        [
            {"id": 1, "name": "Security Key", "price_cents": 3500},
            {"id": 2, "name": "Laptop Sleeve", "price_cents": 2400},
        ],
    )
    seed_connection.execute(
        users_table.insert(),
        {
            "id": 1,
            "username": "shopper@example.com",
            "password_salt": _seed_salt,
            "password_hash": _password_hash(_seed_password, _seed_salt),
        },
    )
del _seed_password


def list_products() -> list[dict[str, int | str]]:
    statement = select([products_table]).order_by(products_table.c.id)
    with engine.connect() as connection:
        rows = connection.execute(statement).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "price_cents": row["price_cents"],
        }
        for row in rows
    ]


def _load_login_record(
    connection: Connection,
    credentials: Credentials,
):
    statement = text(
        "SELECT id, username, password_salt, password_hash FROM users "
        "WHERE username = :username"
    )
    return connection.execute(
        statement,
        {"username": credentials.username},
    ).fetchone()


def authenticate(credentials: Credentials) -> UserRecord | None:
    with engine.connect() as connection:
        row = _load_login_record(connection, credentials)
    if row is None:
        return None

    candidate_hash = _password_hash(credentials.password, row["password_salt"])
    if not hmac.compare_digest(candidate_hash, row["password_hash"]):
        return None
    return UserRecord(id=row["id"], username=row["username"])


def issue_access_token(user: UserRecord) -> str:
    encoded = jwt.encode(
        {"alg": "HS256"},
        {"sub": str(user.id), "username": user.username},
        _token_key,
    )
    return encoded.decode()
