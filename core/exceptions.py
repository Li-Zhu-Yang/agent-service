"""全局异常定义（纯领域层，不依赖 Web 框架）。

FastAPI 异常处理器见 api/error_handlers.py。
"""
from __future__ import annotations


class AppError(Exception):
    """业务异常基类。"""

    def __init__(self, message: str, code: str = "bad_request", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在"):
        super().__init__(message, code="not_found", status_code=404)


class AuthError(AppError):
    def __init__(self, message: str = "未认证或登录已过期"):
        super().__init__(message, code="unauthorized", status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "没有权限"):
        super().__init__(message, code="forbidden", status_code=403)


class RateLimitError(AppError):
    def __init__(self, message: str = "请求过于频繁，请稍后再试"):
        super().__init__(message, code="rate_limited", status_code=429)


class LLMError(AppError):
    def __init__(self, message: str = "大模型服务异常"):
        super().__init__(message, code="llm_error", status_code=502)
