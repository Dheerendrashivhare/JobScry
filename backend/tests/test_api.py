"""Phase 4 backend API tests: profiles/skills, credentials, settings, providers,
searches, resumes — plus per-user ownership isolation. Driven over the ASGI app."""

from __future__ import annotations

from httpx import AsyncClient

API = "/api/v1"


async def _token(client: AsyncClient, email: str, password: str = "supersecret") -> str:
    await client.post(
        f"{API}/auth/register", json={"email": email, "password": password, "full_name": None}
    )
    resp = await client.post(f"{API}/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _hdr(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _new_profile(client: AsyncClient, token: str, **overrides: object) -> dict:
    body = {"name": "Backend — India", **overrides}
    resp = await client.post(f"{API}/profiles", json=body, headers=_hdr(token))
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- profiles + skills ------------------------------------------------------


async def test_first_profile_is_default_with_defaults(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    profile = await _new_profile(client, token)
    assert profile["is_default"] is True
    assert profile["min_score"] == 90
    assert profile["scoring_weights"] == {
        "tech_stack": 40,
        "experience": 20,
        "role": 20,
        "domain": 10,
        "source_quality": 10,
    }
    assert profile["skills"] == []


async def test_create_profile_with_skills_normalizes_names(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    profile = await _new_profile(
        client,
        token,
        skills=[{"name": "FastAPI", "is_required": True}, {"name": "Python"}],
    )
    names = {s["name"] for s in profile["skills"]}
    assert names == {"fastapi", "python"}


async def test_list_profiles_paginated(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    await _new_profile(client, token, name="A")
    await _new_profile(client, token, name="B")
    resp = await client.get(f"{API}/profiles", headers=_hdr(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert body["limit"] == 50 and body["offset"] == 0


async def test_setting_new_default_unsets_previous(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    first = await _new_profile(client, token, name="First")
    second = await _new_profile(client, token, name="Second", is_default=True)
    assert second["is_default"] is True
    again = await client.get(f"{API}/profiles/{first['id']}", headers=_hdr(token))
    assert again.json()["is_default"] is False


async def test_add_then_remove_profile_skill(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    profile = await _new_profile(client, token)
    added = await client.post(
        f"{API}/profiles/{profile['id']}/skills",
        json={"name": "PostgreSQL", "weight": 2.0},
        headers=_hdr(token),
    )
    assert added.status_code == 201
    skill_id = added.json()["skills"][0]["id"]
    removed = await client.delete(
        f"{API}/profiles/{profile['id']}/skills/{skill_id}", headers=_hdr(token)
    )
    assert removed.status_code == 204
    after = await client.get(f"{API}/profiles/{profile['id']}", headers=_hdr(token))
    assert after.json()["skills"] == []


async def test_profile_isolation_between_users(client: AsyncClient) -> None:
    owner = await _token(client, "owner@example.com")  # first -> admin
    other = await _token(client, "other@example.com")
    profile = await _new_profile(client, owner)
    resp = await client.get(f"{API}/profiles/{profile['id']}", headers=_hdr(other))
    assert resp.status_code == 404
    assert resp.json()["code"] == "profile_not_found"


# --- credentials ------------------------------------------------------------


async def test_credential_set_list_masked_and_delete(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    put = await client.put(
        f"{API}/credentials",
        json={"key": "apify_token", "value": "apify_SECRETVALUE1234"},
        headers=_hdr(token),
    )
    assert put.status_code == 200
    assert put.json()["masked_value"] == "****1234"

    listed = await client.get(f"{API}/credentials", headers=_hdr(token))
    assert listed.status_code == 200
    row = listed.json()[0]
    assert row["key"] == "apify_token"
    assert row["masked_value"] == "****1234"
    assert "SECRETVALUE" not in listed.text  # plaintext never leaves

    deleted = await client.delete(f"{API}/credentials/apify_token", headers=_hdr(token))
    assert deleted.status_code == 204
    assert (await client.get(f"{API}/credentials", headers=_hdr(token))).json() == []


async def test_delete_missing_credential_404(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    resp = await client.delete(f"{API}/credentials/jooble_key", headers=_hdr(token))
    assert resp.status_code == 404


# --- settings ---------------------------------------------------------------


async def test_settings_defaults_then_update(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    got = await client.get(f"{API}/settings", headers=_hdr(token))
    assert got.status_code == 200
    body = got.json()
    assert body["theme"] == "dark"
    assert body["notify_cap"] == 20
    assert body["telegram_enabled"] is False

    patched = await client.patch(
        f"{API}/settings",
        json={"notify_cap": 10, "llm_provider": "anthropic", "telegram_enabled": True},
        headers=_hdr(token),
    )
    assert patched.status_code == 200
    assert patched.json()["notify_cap"] == 10
    assert patched.json()["llm_provider"] == "anthropic"
    assert patched.json()["telegram_enabled"] is True


# --- providers --------------------------------------------------------------


async def test_providers_catalog_seeded(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    resp = await client.get(f"{API}/providers", headers=_hdr(token))
    assert resp.status_code == 200
    slugs = {p["slug"] for p in resp.json()}
    assert {"adzuna", "remotive", "apify_linkedin", "apify_naukri"} <= slugs
    assert len(resp.json()) == 8


async def test_admin_toggles_provider_but_user_cannot(client: AsyncClient) -> None:
    admin = await _token(client, "owner@example.com")  # first -> admin
    user = await _token(client, "friend@example.com")

    ok = await client.patch(
        f"{API}/providers/adzuna", json={"is_active": False}, headers=_hdr(admin)
    )
    assert ok.status_code == 200
    assert ok.json()["is_active"] is False

    forbidden = await client.patch(
        f"{API}/providers/adzuna", json={"is_active": True}, headers=_hdr(user)
    )
    assert forbidden.status_code == 403


# --- searches ---------------------------------------------------------------


async def test_create_and_list_search(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    profile = await _new_profile(client, token)
    params = {"titleSearch": ["Backend Engineer"], "descriptionSearch": ["FastAPI"]}
    created = await client.post(
        f"{API}/profiles/{profile['id']}/searches",
        json={"name": "LinkedIn daily", "provider_slug": "apify_linkedin", "params": params},
        headers=_hdr(token),
    )
    assert created.status_code == 201
    assert created.json()["params"] == params

    listed = await client.get(f"{API}/profiles/{profile['id']}/searches", headers=_hdr(token))
    assert listed.json()["total"] == 1


async def test_search_under_unowned_profile_404(client: AsyncClient) -> None:
    owner = await _token(client, "owner@example.com")
    other = await _token(client, "other@example.com")
    profile = await _new_profile(client, owner)
    resp = await client.post(
        f"{API}/profiles/{profile['id']}/searches",
        json={"name": "x"},
        headers=_hdr(other),
    )
    assert resp.status_code == 404


# --- resumes ----------------------------------------------------------------


async def test_upload_resume_first_is_primary(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    profile = await _new_profile(client, token)
    resp = await client.post(
        f"{API}/profiles/{profile['id']}/resumes",
        files={"file": ("cv.pdf", b"%PDF-1.4 fake pdf bytes", "application/pdf")},
        headers=_hdr(token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["format"] == "pdf"
    assert body["parse_status"] == "pending"
    assert body["is_primary"] is True


async def test_upload_unsupported_format_rejected(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    profile = await _new_profile(client, token)
    resp = await client.post(
        f"{API}/profiles/{profile['id']}/resumes",
        files={"file": ("notes.txt", b"just text", "text/plain")},
        headers=_hdr(token),
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "unsupported_resume_format"


async def test_second_resume_then_promote_primary(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    profile = await _new_profile(client, token)
    pid = profile["id"]
    first = await client.post(
        f"{API}/profiles/{pid}/resumes",
        files={"file": ("a.pdf", b"%PDF-1.4 a", "application/pdf")},
        headers=_hdr(token),
    )
    second = await client.post(
        f"{API}/profiles/{pid}/resumes",
        files={"file": ("b.docx", b"PK docx bytes", "application/octet-stream")},
        headers=_hdr(token),
    )
    assert second.json()["is_primary"] is False

    promoted = await client.patch(
        f"{API}/profiles/{pid}/resumes/{second.json()['id']}",
        json={"is_primary": True},
        headers=_hdr(token),
    )
    assert promoted.json()["is_primary"] is True
    first_after = await client.get(
        f"{API}/profiles/{pid}/resumes/{first.json()['id']}", headers=_hdr(token)
    )
    assert first_after.json()["is_primary"] is False


async def test_resume_download_returns_bytes(client: AsyncClient) -> None:
    token = await _token(client, "owner@example.com")
    profile = await _new_profile(client, token)
    content = b"%PDF-1.4 downloadable"
    up = await client.post(
        f"{API}/profiles/{profile['id']}/resumes",
        files={"file": ("cv.pdf", content, "application/pdf")},
        headers=_hdr(token),
    )
    rid = up.json()["id"]
    dl = await client.get(
        f"{API}/profiles/{profile['id']}/resumes/{rid}/download", headers=_hdr(token)
    )
    assert dl.status_code == 200
    assert dl.content == content
