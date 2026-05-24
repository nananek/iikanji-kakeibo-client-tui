"""いいかんじ™家計簿 API クライアント (httpx ベース)"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class APIError(Exception):
    """API 呼び出しのエラー"""

    def __init__(self, status_code: int, message: str, *, error_code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        # OAuth 形式エラーコード (例: authorization_pending, slow_down)
        self.error_code = error_code


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
            error_code: str | None = None
            try:
                payload = resp.json()
                msg = payload.get("error") or str(payload)
                if isinstance(payload, dict) and isinstance(payload.get("error"), str):
                    error_code = payload["error"]
            except Exception:
                msg = resp.text
            raise APIError(resp.status_code, msg, error_code=error_code)
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
        params: dict[str, Any] = {"page": page, "per_page": per_page}
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

    def analyze_image(
        self,
        image_path: str,
        comment: str | None = None,
        *,
        provider: str = "openai",
        llm_api_key: str = "",
        model: str | None = None,
    ) -> dict:
        """E2 PR-D-c: クライアント完結 E2EE フローで画像 AI 解析。

        サーバには画像 + メタデータのみ送信。LLM 呼出はこのプロセスから直接
        行われる。

        Args:
            image_path: 解析する画像ファイルパス
            comment: メモ (省略可)
            provider: "openai" / "anthropic" / "google"
            llm_api_key: 対応 provider の API キー (必須)
            model: 使用モデル名 (省略時はサーバの default_model_by_provider)

        Returns:
            {"draft_id": int, "suggestions": [...]}
        """
        from . import llm

        if not llm_api_key:
            raise APIError(0, f"{provider} の API キーが未設定です。設定画面で API キーを登録してください。")
        if provider not in llm.IMAGE_HANDLERS:
            raise APIError(0, f"未対応の AI provider: {provider}")

        # 1. POST /api/v1/ai/uploads
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        filename = image_path.rsplit("/", 1)[-1]
        mime_type = "image/jpeg"
        if filename.lower().endswith((".png",)):
            mime_type = "image/png"
        elif filename.lower().endswith((".webp",)):
            mime_type = "image/webp"
        elif filename.lower().endswith((".gif",)):
            mime_type = "image/gif"

        files = {"image": (filename, image_bytes, mime_type)}
        data: dict = {}
        if comment:
            data["comment"] = comment
        upload_resp = self.request(
            "POST", "/api/v1/ai/uploads",
            files=files, data=data,
        )
        draft_id = upload_resp["draft_id"]

        # 2. GET /api/v1/ai/prompt-context
        prompt_context = self.request("GET", "/api/v1/ai/prompt-context")

        actual_model = model or prompt_context.get(
            "default_model_by_provider", {}
        ).get(provider)
        if not actual_model:
            raise APIError(0, f"{provider} のデフォルトモデルが取得できません。")

        # 3. Round 1
        compliance_enabled = bool(prompt_context.get("compliance_check_enabled"))
        round1_prompt = llm.build_round1_prompt(
            round1_prompt=prompt_context.get("round1_prompt", ""),
            compliance_check_enabled=compliance_enabled,
            compliance_prompt=prompt_context.get("compliance_prompt", ""),
            custom_prompt=prompt_context.get("custom_prompt", ""),
            comment=comment or "",
        )
        max_tokens_r1 = 1500 if compliance_enabled else 1000
        r1_raw = llm.call_image_llm(
            provider=provider, api_key=llm_api_key, model=actual_model,
            image_bytes=image_bytes, mime_type=mime_type,
            prompt=round1_prompt, max_tokens=max_tokens_r1,
        )
        analysis = llm.parse_document_analysis(r1_raw)
        compliance_result = (
            llm.parse_compliance_result(r1_raw.get("compliance"))
            if compliance_enabled else None
        )

        # 4. needs_ledger なら ledger 取得
        ledger_text = ""
        if analysis.needs_ledger and analysis.requested_accounts:
            try:
                ledger_resp = self.request(
                    "POST", "/api/v1/ai/ledger-context",
                    json={"account_names": analysis.requested_accounts},
                )
                ledger_text = ledger_resp.get("ledger_text", "")
            except APIError:
                pass

        # 5. Round 2
        round2_prompt = llm.build_round2_prompt(
            prompt_context=prompt_context,
            needs_ledger=analysis.needs_ledger,
            ledger_text=ledger_text,
        )
        r2_raw = llm.call_image_llm(
            provider=provider, api_key=llm_api_key, model=actual_model,
            image_bytes=image_bytes, mime_type=mime_type,
            prompt=round2_prompt, max_tokens=2000,
        )
        valid_codes = {
            line.split()[0]
            for line in prompt_context.get("account_list_text", "").split("\n")
            if line.strip() and line.strip()[0].isdigit()
        }
        suggestions = llm.validate_suggestions(r2_raw, valid_codes)
        if compliance_result is not None:
            for s in suggestions:
                s["compliance"] = compliance_result

        # 6. PATCH /api/v1/ai/drafts/<id>/suggestions
        self.request(
            "PATCH", f"/api/v1/ai/drafts/{draft_id}/suggestions",
            json={
                "suggestions": suggestions,
                "provider": provider,
                "model": actual_model,
            },
        )

        return {"draft_id": draft_id, "suggestions": suggestions}

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
