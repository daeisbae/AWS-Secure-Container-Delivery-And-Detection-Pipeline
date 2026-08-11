from __future__ import annotations

from html import escape
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, StringConstraints
from sqlalchemy.exc import SQLAlchemyError

from app.store import authenticate, issue_access_token, list_products


class HealthResponse(BaseModel):
    status: str


class Product(BaseModel):
    id: int
    name: str
    price_cents: int


class LoginRequest(BaseModel):
    username: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=3, max_length=64),
    ]
    password: Annotated[str, StringConstraints(min_length=8, max_length=128)]


class LoginResponse(BaseModel):
    access_token: str
    token_type: str


app = FastAPI(title="Pipeline Security Shop", version="1.0.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/products", response_model=list[Product])
def products() -> list[Product]:
    return [Product(**item) for item in list_products()]


@app.get("/search", response_class=HTMLResponse)
def search(
    q: Annotated[str, Query(min_length=1, max_length=128)],
) -> HTMLResponse:
    safe_query = escape(q)
    # Experiment 3 intentionally omits browser security headers from this HTML
    # response so ZAP can report the resulting configuration findings.
    return HTMLResponse(
        "<!doctype html><html lang=\"en\"><head>"
        "<meta charset=\"utf-8\"><title>Product search</title></head>"
        f"<body><h1>Product search</h1><p>Results for: {safe_query}</p></body></html>"
    )


@app.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest) -> LoginResponse:
    try:
        user = authenticate(credentials)
    except SQLAlchemyError:
        user = None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return LoginResponse(
        access_token=issue_access_token(user),
        token_type="bearer",
    )
