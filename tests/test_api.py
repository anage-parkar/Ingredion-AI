"""The api service's platform behaviour: authentication, liveness, headers, CORS,
and the absence of anything but the two agents' surfaces."""

from __future__ import annotations

import json

from conftest import headers


def test_missing_or_wrong_api_key_is_401(client):
    assert client.get("/api/order-intake/review/items").status_code == 401
    assert client.get("/api/prebill/review/items", headers=headers(key="nope")).status_code == 401
    body = client.get("/api/order-intake/ops/kill-switch").json()
    assert body == {"error": "Invalid or missing API key", "success": False}


def test_missing_user_header_is_400(client):
    assert client.get("/api/order-intake/review/items", headers={"X-API-Key": "test-service-key"}).status_code == 400


def test_api_key_in_query_string_is_not_accepted(client):
    r = client.get("/api/order-intake/review/items?api_key=test-service-key", headers={"X-User-Id": "u"})
    assert r.status_code == 401


def test_liveness_is_public_and_names_the_agents_served(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["agents"] == ["order-intake", "prebill"]


def test_the_surface_is_the_two_agents_and_nothing_else(client):
    spec = client.get("/openapi.json").json()
    paths = sorted(spec["paths"])
    assert paths == [
        "/api/order-intake/ops/health", "/api/order-intake/ops/kill-switch", "/api/order-intake/ops/poll",
        "/api/order-intake/review/items", "/api/order-intake/review/items/{item_id}", "/api/order-intake/review/items/{item_id}/decision",
        "/api/prebill/ops/health", "/api/prebill/ops/kill-switch", "/api/prebill/ops/poll",
        "/api/prebill/review/items", "/api/prebill/review/items/{item_id}", "/api/prebill/review/items/{item_id}/decision",
        "/events/order-intake/cases", "/events/prebill/invoices", "/health",
    ]
    assert "foundry" not in json.dumps(spec).lower() and "azure" not in json.dumps(spec).lower()
    assert client.get("/api/agent/conversations", headers=headers()).status_code == 404


def test_security_headers_everywhere_but_docs_keep_working(client):
    api = client.get("/health")
    assert api.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in api.headers["content-security-policy"]
    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "content-security-policy" not in docs.headers


def test_cors_preflight_for_configured_origin(client):
    r = client.options(
        "/api/order-intake/review/items",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type,x-api-key,x-user-id",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    bad = client.options(
        "/api/order-intake/review/items",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"},
    )
    assert bad.status_code == 400
