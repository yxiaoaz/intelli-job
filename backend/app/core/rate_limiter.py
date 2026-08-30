"""slowapi 限流：三档分档（auth / 通用 default_limits / AI 重接口）+ 反代 key 适配。

分档端点映射见 openspec/changes/api-abuse-protection/design.md 1.2。
"""

from fastapi import Request
from slowapi import Limiter

from app.config import get_settings

settings = get_settings()


def client_key(request: Request) -> str:
    """限流 key：优先取 X-Forwarded-For 最右侧 IP，无则退回 remote addr。

    生产流量经 Caddy 反代转发到 127.0.0.1，uvicorn 看到的 remote address
    恒为 127.0.0.1——默认 get_remote_address 会让全站共享一把限流锁。
    XFF 是逐跳追加列表：客户端可伪造整条头，但伪造值只能出现在左侧，
    可信代理（Caddy）把真实客户端 IP 追加在尾部 → 必须取最右侧，绝不能取第一个。
    """
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(
    key_func=client_key,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],  # 通用档兜底
)

# 预构建分档装饰器（import 时从 settings 读值，改 env 重启生效，与项目配置生效模式一致）
auth_limit = limiter.limit(f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute")
ai_limit = limiter.limit(f"{settings.RATE_LIMIT_AI_PER_MINUTE}/minute")
