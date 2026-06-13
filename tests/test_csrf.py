"""Testy ochrony CSRF."""

import pytest


def test_csrf_get_login_sets_cookie(client):
    """GET /auth/logowanie powinien ustawić ciasteczko csrf_token."""
    resp = client.get("/auth/logowanie")
    assert resp.status_code == 200
    csrf = resp.cookies.get("csrf_token", "")
    assert csrf, "Brak ciasteczka CSRF"
    assert "." in csrf, "Ciasteczko CSRF powinno być podpisane"


def test_csrf_post_without_token_returns_403(client):
    """POST logowanie bez tokenu CSRF → 403."""
    resp = client.post(
        "/auth/logowanie",
        data={"email": "test@example.com", "password": "pass123"},
    )
    assert resp.status_code == 403
    assert "CSRF" in resp.text or "csrf" in resp.text.lower()


def test_csrf_post_with_valid_token_succeeds(client_with_csrf):
    """POST logowanie z ważnym tokenem CSRF → nie blokowane przez CSRF.

    (logowanie i tak zwróci 302 lub błąd walidacji, ale nie 403)
    """
    client, token = client_with_csrf
    resp = client.post(
        "/auth/logowanie",
        data={"email": "admin@test.pl", "password": "TestAdmin123!"},
        headers={"X-CSRF-Token": token},
    )
    assert resp.status_code != 403, "CSRF nie powinien blokować z poprawnym tokenem"
    # 302 = przekierowanie po udanym logowaniu
    # 200 = strona z błędem (nieprawidłowe dane)


def test_csrf_post_with_wrong_token_returns_403(client):
    """POST z nieprawidłowym tokenem CSRF → 403."""
    # Najpierw zdobądź ciasteczko
    get_resp = client.get("/auth/logowanie")
    assert get_resp.status_code == 200

    # POST z nieprawidłowym tokenem
    resp = client.post(
        "/auth/logowanie",
        data={"email": "test@example.com", "password": "pass123"},
        headers={"X-CSRF-Token": "invalid-token-value"},
    )
    assert resp.status_code == 403


def test_csrf_healthcheck_exempt(client):
    """GET /health nie wymaga CSRF (bezpieczny endpoint)."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_csrf_landing_no_csrf_needed(client):
    """GET / (landing page) nie wymaga CSRF."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_csrf_register_post_with_csrf(client_with_csrf):
    """POST /auth/rejestracja z CSRF → nie blokowane (walidacja danych, ale nie 403)."""
    client, token = client_with_csrf
    resp = client.post(
        "/auth/rejestracja",
        data={
            "email": "test@example.com",
            "password": "StrongPass123!",
            "name": "Test User",
            "slug": "test-user",
        },
        headers={"X-CSRF-Token": token},
    )
    assert resp.status_code != 403, "CSRF nie powinien blokować z poprawnym tokenem"
