"""OAuth Device Flow クライアントのテスト"""

from __future__ import annotations

import io

import click
import httpx
import pytest
import respx

from iikanji_tui.auth import perform_device_flow


BASE = "https://example.com"


def _device_response(user_code="WXYZ-1234"):
    return httpx.Response(200, json={
        "device_code": "raw_device_code_xxxx",
        "user_code": user_code,
        "verification_uri": f"{BASE}/oauth/device",
        "verification_uri_complete": f"{BASE}/oauth/device?code={user_code}",
        "expires_in": 600,
        "interval": 1,
    })


def _pending(extra: dict | None = None):
    body = {"error": "authorization_pending"}
    if extra:
        body.update(extra)
    return httpx.Response(400, json=body)


def _slow_down():
    return httpx.Response(400, json={"error": "slow_down"})


def _denied():
    return httpx.Response(400, json={"error": "access_denied"})


def _expired():
    return httpx.Response(400, json={"error": "expired_token"})


def _granted(token="ikt_secret"):
    return httpx.Response(200, json={
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": 31536000,
    })


class TestSuccessFlow:
    @respx.mock
    def test_returns_token_on_first_grant(self):
        respx.post(f"{BASE}/oauth/device").mock(return_value=_device_response())
        respx.post(f"{BASE}/oauth/token").mock(return_value=_granted("ikt_xxx"))
        out = io.StringIO()
        sleeps: list[float] = []

        token = perform_device_flow(
            BASE, open_browser=False, out=out, sleep=sleeps.append,
        )
        assert token == "ikt_xxx"
        assert "WXYZ-1234" in out.getvalue()
        assert sleeps == [1]

    @respx.mock
    def test_polls_until_approval(self):
        respx.post(f"{BASE}/oauth/device").mock(return_value=_device_response())
        respx.post(f"{BASE}/oauth/token").mock(side_effect=[
            _pending(), _pending(), _granted("ikt_y"),
        ])
        sleeps: list[float] = []
        token = perform_device_flow(
            BASE, open_browser=False, out=io.StringIO(), sleep=sleeps.append,
        )
        assert token == "ikt_y"
        assert sleeps == [1, 1, 1]

    @respx.mock
    def test_slow_down_increases_interval(self):
        respx.post(f"{BASE}/oauth/device").mock(return_value=_device_response())
        respx.post(f"{BASE}/oauth/token").mock(side_effect=[
            _slow_down(), _granted(),
        ])
        sleeps: list[float] = []
        perform_device_flow(
            BASE, open_browser=False, out=io.StringIO(), sleep=sleeps.append,
        )
        # 初回 sleep=1, slow_down 受信後 +5 で sleep=6
        assert sleeps == [1, 6]


class TestErrorCases:
    @respx.mock
    def test_access_denied_raises_click_exception(self):
        respx.post(f"{BASE}/oauth/device").mock(return_value=_device_response())
        respx.post(f"{BASE}/oauth/token").mock(return_value=_denied())
        with pytest.raises(click.ClickException) as exc:
            perform_device_flow(
                BASE, open_browser=False, out=io.StringIO(), sleep=lambda _: None,
            )
        assert "拒否" in str(exc.value.message)

    @respx.mock
    def test_expired_token_raises(self):
        respx.post(f"{BASE}/oauth/device").mock(return_value=_device_response())
        respx.post(f"{BASE}/oauth/token").mock(return_value=_expired())
        with pytest.raises(click.ClickException) as exc:
            perform_device_flow(
                BASE, open_browser=False, out=io.StringIO(), sleep=lambda _: None,
            )
        assert "期限切れ" in str(exc.value.message)

    @respx.mock
    def test_unexpected_500_raises(self):
        respx.post(f"{BASE}/oauth/device").mock(return_value=_device_response())
        respx.post(f"{BASE}/oauth/token").mock(
            return_value=httpx.Response(500, text="internal")
        )
        with pytest.raises(click.ClickException):
            perform_device_flow(
                BASE, open_browser=False, out=io.StringIO(), sleep=lambda _: None,
            )


class TestUserMessages:
    @respx.mock
    def test_displays_url_and_code(self):
        respx.post(f"{BASE}/oauth/device").mock(
            return_value=_device_response(user_code="ABCD-EFGH")
        )
        respx.post(f"{BASE}/oauth/token").mock(return_value=_granted())
        out = io.StringIO()
        perform_device_flow(
            BASE, open_browser=False, out=out, sleep=lambda _: None,
        )
        text = out.getvalue()
        assert "ABCD-EFGH" in text
        assert "/oauth/device" in text

    @respx.mock
    def test_displays_qr_by_default(self):
        respx.post(f"{BASE}/oauth/device").mock(return_value=_device_response())
        respx.post(f"{BASE}/oauth/token").mock(return_value=_granted())
        out = io.StringIO()
        perform_device_flow(
            BASE, open_browser=False, out=out, sleep=lambda _: None,
        )
        text = out.getvalue()
        # qrcode の ASCII アートには Unicode 半角ブロックや white square が含まれる
        assert "QR" in text
        # 何らかの QR ブロック文字（█ または ▀ または ▄ など）
        assert any(c in text for c in "█▀▄ ")

    @respx.mock
    def test_show_qr_false_skips_qr(self):
        respx.post(f"{BASE}/oauth/device").mock(return_value=_device_response())
        respx.post(f"{BASE}/oauth/token").mock(return_value=_granted())
        out = io.StringIO()
        perform_device_flow(
            BASE, open_browser=False, show_qr=False,
            out=out, sleep=lambda _: None,
        )
        assert "QR" not in out.getvalue()


class TestRenderQr:
    def test_returns_non_empty_ascii(self):
        from iikanji_tui.auth import render_qr_ascii
        art = render_qr_ascii("https://example.com/oauth/device?code=ABCD-EFGH")
        assert art
        # 複数行
        assert art.count("\n") > 5


class TestLoginCommand:
    """`iikanji-tui login` の統合"""

    @respx.mock
    def test_login_saves_token_to_config(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        respx.post(f"{BASE}/oauth/device").mock(return_value=_device_response())
        respx.post(f"{BASE}/oauth/token").mock(return_value=_granted("ikt_login_test"))

        # webbrowser.open / time.sleep は無効化
        import iikanji_tui.auth as auth_mod
        monkeypatch.setattr(auth_mod, "time", auth_mod.time)
        monkeypatch.setattr("webbrowser.open", lambda *a, **k: True)

        from click.testing import CliRunner
        from iikanji_tui.cli import main

        runner = CliRunner()
        # auth_mod の sleep を差し替え
        original = auth_mod.perform_device_flow
        def fast_flow(api_url, **kwargs):
            kwargs.setdefault("open_browser", False)
            kwargs.setdefault("sleep", lambda _: None)
            return original(api_url, **kwargs)
        monkeypatch.setattr(auth_mod, "perform_device_flow", fast_flow)
        # cli.login が import している関数も差し替える
        import iikanji_tui.cli as cli_mod
        monkeypatch.setattr(cli_mod, "perform_device_flow", fast_flow)

        result = runner.invoke(main, ["login", "--api-url", BASE])
        assert result.exit_code == 0, result.output

        from iikanji_tui.config import load_config
        config = load_config()
        assert config.api_url == BASE
        assert config.access_token == "ikt_login_test"
