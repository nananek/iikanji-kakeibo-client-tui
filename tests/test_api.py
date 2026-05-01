"""API クライアントのテスト"""

from __future__ import annotations

import httpx
import pytest
import respx

from iikanji_tui.api import APIClient, APIError


BASE = "https://example.com"


class TestAuthHeader:
    @respx.mock
    def test_includes_bearer_when_token_set(self):
        route = respx.get(f"{BASE}/api/v1/journals").mock(
            return_value=httpx.Response(200, json={"ok": True, "journals": [], "total": 0})
        )
        client = APIClient(base_url=BASE, access_token="ikt_abc")
        client.list_journals()
        assert route.called
        sent = route.calls[0].request
        assert sent.headers["Authorization"] == "Bearer ikt_abc"

    @respx.mock
    def test_omits_bearer_for_oauth_device(self):
        route = respx.post(f"{BASE}/oauth/device").mock(
            return_value=httpx.Response(200, json={
                "device_code": "d", "user_code": "U-C",
                "verification_uri": f"{BASE}/oauth/device",
                "verification_uri_complete": f"{BASE}/oauth/device?code=U-C",
                "expires_in": 600, "interval": 5,
            })
        )
        client = APIClient(base_url=BASE, access_token="ikt_should_not_be_sent")
        client.oauth_device("test-cli")
        sent = route.calls[0].request
        assert "Authorization" not in sent.headers


class TestErrorHandling:
    @respx.mock
    def test_4xx_raises_api_error_with_message(self):
        respx.get(f"{BASE}/api/v1/journals").mock(
            return_value=httpx.Response(401, json={"error": "無効な API キーです。"})
        )
        client = APIClient(base_url=BASE, access_token="ikt_x")
        with pytest.raises(APIError) as exc:
            client.list_journals()
        assert exc.value.status_code == 401
        assert "無効な" in exc.value.message

    @respx.mock
    def test_4xx_with_non_json_body(self):
        respx.get(f"{BASE}/api/v1/journals").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        client = APIClient(base_url=BASE, access_token="ikt_x")
        with pytest.raises(APIError):
            client.list_journals()


class TestOAuthEndpoints:
    @respx.mock
    def test_oauth_device_request_body(self):
        route = respx.post(f"{BASE}/oauth/device").mock(
            return_value=httpx.Response(200, json={
                "device_code": "d", "user_code": "U-C",
                "verification_uri": f"{BASE}/oauth/device",
                "verification_uri_complete": "x",
                "expires_in": 600, "interval": 5,
            })
        )
        client = APIClient(base_url=BASE)
        result = client.oauth_device("my-tui")
        assert result["device_code"] == "d"
        assert route.calls[0].request.read() == b'{"client_name":"my-tui"}'

    @respx.mock
    def test_oauth_token_uses_form_encoded(self):
        route = respx.post(f"{BASE}/oauth/token").mock(
            return_value=httpx.Response(200, json={
                "access_token": "ikt_xxx",
                "token_type": "Bearer",
                "expires_in": 31536000,
            })
        )
        client = APIClient(base_url=BASE)
        result = client.oauth_token("device_code_123")
        assert result["access_token"] == "ikt_xxx"
        body = route.calls[0].request.read()
        assert b"grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Adevice_code" in body
        assert b"device_code=device_code_123" in body


class TestJournalEndpoints:
    @respx.mock
    def test_list_journals_with_pagination(self):
        route = respx.get(f"{BASE}/api/v1/journals").mock(
            return_value=httpx.Response(200, json={
                "ok": True, "journals": [], "total": 0, "page": 1, "per_page": 20,
            })
        )
        client = APIClient(base_url=BASE, access_token="ikt_x")
        client.list_journals(page=2, per_page=50, date_from="2026-01-01")
        params = route.calls[0].request.url.params
        assert params["page"] == "2"
        assert params["per_page"] == "50"
        assert params["date_from"] == "2026-01-01"

    @respx.mock
    def test_create_journal(self):
        route = respx.post(f"{BASE}/api/v1/journals").mock(
            return_value=httpx.Response(201, json={
                "ok": True, "id": 42, "entry_number": 5,
            })
        )
        client = APIClient(base_url=BASE, access_token="ikt_x")
        result = client.create_journal(
            date="2026-01-15",
            description="食費",
            lines=[
                {"account_code": "5010", "debit": 1000, "credit": 0},
                {"account_code": "1010", "debit": 0, "credit": 1000},
            ],
        )
        assert result["id"] == 42
        assert route.calls[0].request.method == "POST"

    @respx.mock
    def test_delete_journal(self):
        respx.delete(f"{BASE}/api/v1/journals/42").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )
        client = APIClient(base_url=BASE, access_token="ikt_x")
        result = client.delete_journal(42)
        assert result["ok"] is True
