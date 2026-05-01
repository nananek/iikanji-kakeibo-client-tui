"""いいかんじ™家計簿 API クライアント (httpx ベース)"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class APIError(Exception):
    """API 呼び出しのエラー"""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass
class APIClient:
    """同期版 API クライアント"""

    base_url: str
    access_token: str = ""
    timeout: float = 30.0

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json"}
        if self.access_token:
            h["Authorization"] = f"Bearer {self.access_token}"
        return h

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def request(
        self, method: str, path: str, *,
        json: Any = None, params: dict | None = None,
        data: Any = None, files: Any = None,
        auth_required: bool = True,
    ) -> Any:
        url = self._url(path)
        headers = self._headers()
        if not auth_required:
            headers.pop("Authorization", None)
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.request(
                method, url, headers=headers,
                json=json, params=params, data=data, files=files,
            )
        if resp.status_code >= 400:
            try:
                payload = resp.json()
                msg = payload.get("error") or str(payload)
            except Exception:
                msg = resp.text
            raise APIError(resp.status_code, msg)
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return resp.content

    # --- OAuth Device Flow ---

    def oauth_device(self, client_name: str = "iikanji-tui") -> dict:
        return self.request(
            "POST", "/oauth/device",
            json={"client_name": client_name},
            auth_required=False,
        )

    def oauth_token(self, device_code: str) -> dict:
        return self.request(
            "POST", "/oauth/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
            },
            auth_required=False,
        )

    # --- 仕訳 ---

    def list_journals(self, page: int = 1, per_page: int = 20,
                      date_from: str | None = None, date_to: str | None = None) -> dict:
        params = {"page": page, "per_page": per_page}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return self.request("GET", "/api/v1/journals", params=params)

    def get_journal(self, entry_id: int) -> dict:
        return self.request("GET", f"/api/v1/journals/{entry_id}")

    def create_journal(self, *, date: str, description: str, lines: list[dict],
                       source: str = "api", draft_id: int | None = None) -> dict:
        body: dict[str, Any] = {
            "date": date, "description": description,
            "lines": lines, "source": source,
        }
        if draft_id is not None:
            body["draft_id"] = draft_id
        return self.request("POST", "/api/v1/journals", json=body)

    def delete_journal(self, entry_id: int) -> dict:
        return self.request("DELETE", f"/api/v1/journals/{entry_id}")

    # --- AI ---

    def list_drafts(self, status: str = "analyzed") -> dict:
        return self.request("GET", "/api/v1/ai/drafts", params={"status": status})

    def get_draft(self, draft_id: int) -> dict:
        return self.request("GET", f"/api/v1/ai/drafts/{draft_id}")

    def delete_draft(self, draft_id: int) -> dict:
        return self.request("DELETE", f"/api/v1/ai/drafts/{draft_id}")

    def analyze_image(self, image_path: str, comment: str | None = None) -> dict:
        with open(image_path, "rb") as f:
            files = {"image": (image_path.rsplit("/", 1)[-1], f)}
            data: dict = {}
            if comment:
                data["comment"] = comment
            return self.request(
                "POST", "/api/v1/ai/analyze",
                files=files, data=data,
            )

    # --- 証憑 ---

    def list_vouchers(self, page: int = 1, per_page: int = 20,
                      search: str | None = None) -> dict:
        params: dict = {"page": page, "per_page": per_page}
        if search:
            params["search"] = search
        return self.request("GET", "/api/v1/vouchers", params=params)

    def get_voucher_image(self, voucher_id: int) -> bytes:
        return self.request("GET", f"/api/v1/vouchers/{voucher_id}/image")

    def verify_voucher(self, voucher_id: int) -> dict:
        return self.request("GET", f"/api/v1/vouchers/{voucher_id}/verify")
