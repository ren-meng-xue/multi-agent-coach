"""自定义业务异常类，各层直接 raise，由全局 handler 统一转换为 Response。"""


class AppException(Exception):
    """业务异常基类，携带 HTTP 状态码和消息。"""

    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        self.message = message


class BadRequestException(AppException):
    """400 - 请求参数不合法。"""

    def __init__(self, message: str = "请求参数错误"):
        super().__init__(status_code=400, message=message)


class UnauthorizedException(AppException):
    """401 - 未登录或 token 无效。"""

    def __init__(self, message: str = "未授权，请先登录"):
        super().__init__(status_code=401, message=message)


class ForbiddenException(AppException):
    """403 - 无访问权限。"""

    def __init__(self, message: str = "无权限访问"):
        super().__init__(status_code=403, message=message)


class NotFoundException(AppException):
    """404 - 资源不存在。"""

    def __init__(self, message: str = "资源不存在"):
        super().__init__(status_code=404, message=message)


class ConflictException(AppException):
    """409 - 数据冲突（如重复创建）。"""

    def __init__(self, message: str = "数据冲突"):
        super().__init__(status_code=409, message=message)


class InternalServerException(AppException):
    """500 - 服务器内部错误，由全局兜底 handler 捕获。"""

    def __init__(self, message: str = "服务器内部错误"):
        super().__init__(status_code=500, message=message)
