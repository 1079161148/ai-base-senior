"""S9 · 鉴权模型。"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    # 最短 6 位：学习项目取「不烦人」和「不是空密码」的折中。
    # 真要上生产应该接 zxcvbn 之类的强度评估，而不是位数检查。
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=64)


class UserOut(BaseModel):
    id: str
    username: str
    display_name: str = ""


class TokenOut(BaseModel):
    """登录成功的返回。前端把它存 localStorage，之后每个请求带 Authorization。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
