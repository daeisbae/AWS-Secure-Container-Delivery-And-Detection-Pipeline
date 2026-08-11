from __future__ import annotations

import os

import authlib
import sqlalchemy
from fastapi.testclient import TestClient

from app.main import app

_DEMO_PASSWORD = os.environ["SHOP_DEMO_PASSWORD"]


def test_deliberate_production_dependency_versions() -> None:
    assert authlib.__version__ == "1.6.8"
    assert sqlalchemy.__version__ == "1.2.17"


def test_health_returns_exact_response() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_products_return_the_demo_catalog() -> None:
    with TestClient(app) as client:
        response = client.get("/products")

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "name": "Security Key", "price_cents": 3500},
        {"id": 2, "name": "Laptop Sleeve", "price_cents": 2400},
    ]


def test_product_search_escapes_html() -> None:
    query = '<script>alert("xss")</script>'

    with TestClient(app) as client:
        response = client.get("/search", params={"q": query})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert query not in response.text
    assert "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;" in response.text


def test_product_search_omits_security_headers_for_experiment_3() -> None:
    with TestClient(app) as client:
        response = client.get("/search", params={"q": "keyboard"})

    assert "content-security-policy" not in response.headers
    assert "x-frame-options" not in response.headers
    assert "x-content-type-options" not in response.headers


def test_product_search_requires_a_bounded_query() -> None:
    with TestClient(app) as client:
        missing = client.get("/search")
        oversized = client.get("/search", params={"q": "q" * 129})

    assert missing.status_code == 422
    assert oversized.status_code == 422


def test_login_rejects_credentials_without_echoing_them() -> None:
    username = "shopper@example.com"
    password = "not-a-real-password"

    with TestClient(app) as client:
        response = client.post(
            "/login",
            json={"username": username, "password": password},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}
    assert username not in response.text
    assert password not in response.text


def test_login_validates_field_lengths() -> None:
    with TestClient(app) as client:
        blank = client.post("/login", json={"username": " ", "password": " "})
        oversized = client.post(
            "/login",
            json={"username": "u" * 65, "password": "p" * 129},
        )

    assert blank.status_code == 422
    assert oversized.status_code == 422


def test_login_returns_an_authlib_token_for_the_seeded_user() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/login",
            json={
                "username": "shopper@example.com",
                "password": _DEMO_PASSWORD,
            },
        )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"].count(".") == 2
