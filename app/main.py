from __future__ import annotations

from collections.abc import Awaitable, Callable
from html import escape
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, StringConstraints
from sqlalchemy.exc import SQLAlchemyError

from app.store import authenticate, issue_access_token, list_products


_SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'; frame-ancestors 'none'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
}


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


@app.middleware("http")
async def add_security_headers(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    response = await call_next(request)
    for name, value in _SECURITY_HEADERS.items():
        response.headers[name] = value
    return response


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
