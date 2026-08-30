"""限流层单测（api-abuse-protection Phase 2）。

用独立 Limiter 实例构建 mini-app，不污染主 app 的共享计数；
client_key 的反代语义（XFF 最右侧）用纯函数直测。
"""

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from httpx import AsyncClient, ASGITransport
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request as StarletteRequest

from app.core.rate_limiter import client_key


# ── client_key 纯函数：XFF 最右侧语义 ─────────────────────────────────────


def _make_request(xff: str | None = None, client=("1.2.3.4", 123)):
    headers = []
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode()))
    scope = {"type": "http", "headers": headers, "client": client}
    return StarletteRequest(scope)


class TestClientKey:

    def test_no_xff_falls_back_to_remote_addr(self):
        assert client_key(_make_request()) == "1.2.3.4"

    def test_no_xff_no_client_unknown(self):
        assert client_key(_make_request(client=None)) == "unknown"

    def test_takes_rightmost_xff(self):
        """客户端伪造的值只能在左侧，可信代理（Caddy）追加在尾部"""
        assert client_key(_make_request("1.2.3.4, 5.6.7.8")) == "5.6.7.8"

    def test_strips_whitespace(self):
        assert client_key(_make_request("1.2.3.4,  5.6.7.8 ")) == "5.6.7.8"

    def test_single_xff_value(self):
        assert client_key(_make_request("9.9.9.9")) == "9.9.9.9"


# ── mini-app 集成：分档 429 / 豁免 / SSE 429 为正常 HTTP 响应 ─────────────


def _make_app() -> FastAPI:
    """独立 Limiter（内存存储），低阈值便于触发"""
    test_limiter = Limiter(key_func=client_key, default_limits=["3/minute"])
    app = FastAPI()
    app.state.limiter = test_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    @app.get("/ping")
    @test_limiter.exempt
    async def ping(request: Request):
        return {"ok": True}

    @app.get("/limited")
    async def limited(request: Request):
        return {"ok": True}

    @app.get("/sse")
    @test_limiter.limit("2/minute")
    async def sse(request: Request):
        async def gen():
            yield "data: hi\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


@pytest.fixture
def mini_app():
    return _make_app()


@pytest_asyncio.fixture
async def mini_client(mini_app):
    async with AsyncClient(
        transport=ASGITransport(app=mini_app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
class TestRateLimitIntegration:

    async def test_default_limit_triggers_429(self, mini_client):
        for _ in range(3):
            resp = await mini_client.get("/limited", headers={"X-Forwarded-For": "1.1.1.1"})
            assert resp.status_code == 200
        resp = await mini_client.get("/limited", headers={"X-Forwarded-For": "1.1.1.1"})
        assert resp.status_code == 429

    async def test_keys_are_isolated_by_xff(self, mini_client):
        """不同 XFF 各自计数，互不干扰（反代下 key 区分度）"""
        for _ in range(3):
            resp = await mini_client.get("/limited", headers={"X-Forwarded-For": "2.2.2.2"})
            assert resp.status_code == 200
        # 另一个 IP 仍有独立额度
        resp = await mini_client.get("/limited", headers={"X-Forwarded-For": "3.3.3.3"})
        assert resp.status_code == 200

    async def test_forged_xff_uses_rightmost(self, mini_client):
        """伪造 XFF 取最右侧（攻击者自填的第一个值不生效）"""
        for _ in range(3):
            resp = await mini_client.get(
                "/limited", headers={"X-Forwarded-For": "4.4.4.4, 5.5.5.5"}
            )
            assert resp.status_code == 200
        # 第 4 次：key=5.5.5.5 超限
        resp = await mini_client.get(
            "/limited", headers={"X-Forwarded-For": "4.4.4.4, 5.5.5.5"}
        )
        assert resp.status_code == 429
        # 换最右侧 IP → 新的独立额度（证明 key 取的是最右侧）
        resp = await mini_client.get(
            "/limited", headers={"X-Forwarded-For": "4.4.4.4, 6.6.6.6"}
        )
        assert resp.status_code == 200

    async def test_exempt_endpoint_never_429(self, mini_client):
        """/health 豁免：高频探测不占额度"""
        for _ in range(10):
            resp = await mini_client.get("/ping", headers={"X-Forwarded-For": "7.7.7.7"})
            assert resp.status_code == 200

    async def test_sse_429_is_http_response_not_stream(self, mini_client):
        """SSE 端点限流触发的 429 是正常 HTTP 响应，而非进入 SSE 流"""
        for _ in range(2):
            resp = await mini_client.get("/sse", headers={"X-Forwarded-For": "8.8.8.8"})
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
        resp = await mini_client.get("/sse", headers={"X-Forwarded-For": "8.8.8.8"})
        assert resp.status_code == 429
        assert not resp.headers["content-type"].startswith("text/event-stream")
