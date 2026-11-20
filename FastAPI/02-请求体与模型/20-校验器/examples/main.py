"""第 20 章 · 校验器（field_validator / model_validator）。

核心：`Field` 只能表达「单个字段」的约束；跨字段规则（两次密码一致、结束不早于开始）
      与「值变形」（去空格、空串转 None）要用校验器，并且要清楚错误落在哪个 loc。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from datetime import date
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

app = FastAPI(title="第 20 章 · 校验器", version="0.1.0")


# ============================================================
# 1. 带字段级 + 模型级校验的请求模型
# ============================================================
class BookingCreate(BaseModel):
    """预约创建：演示三类校验器用法。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=5, max_length=64)
    password: str = Field(min_length=1)
    confirm: str = Field(min_length=1)
    start: date
    end: date
    guests: int = Field(ge=1, le=10)
    note: str | None = None

    # --------------------------------------------------------
    # ① 字段校验器（after，默认）：此时字段已经通过类型与 Field 约束
    # --------------------------------------------------------
    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """【作用】把邮箱统一成小写，避免同一邮箱出现两种写法

        【注意】这里再抛 ValueError，422 的 loc 会指向 `["body","email"]`
        【注意】`ValueError` 的 message 在响应里会带 `Value error, ` 前缀（实测）
        """
        if "@" not in value:
            raise ValueError("邮箱必须包含 @")
        return value.lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        """【作用】多个条件可以合并成一个校验器，错误信息写给用户看"""
        if len(value) < 8:
            raise ValueError("密码至少 8 位")
        if value.isdigit():
            raise ValueError("密码不能全是数字")
        return value

    # --------------------------------------------------------
    # ② 字段校验器（before）：拿到的是「原始输入」，可做变形
    # --------------------------------------------------------
    @field_validator("note", mode="before")
    @classmethod
    def blank_note_to_none(cls, value: Any) -> Any:
        """【作用】把空字符串/纯空格转成 None

        【为什么】前端表单「没填」常提交 `""`，而库里希望存 NULL
        【注意】mode="before" 时字段类型还没转换，`value` 可能是任何类型
        """
        if isinstance(value, str) and not value.strip():
            return None
        return value

    # --------------------------------------------------------
    # ③ 模型校验器（after）：能访问所有字段，用于跨字段规则
    # --------------------------------------------------------
    @model_validator(mode="after")
    def check_business_rules(self) -> "BookingCreate":
        """【作用】跨字段校验，`Field` 完全做不到的部分

        【实测】这里抛 ValueError，422 的 loc 是 `["body"]`（整个模型），不是某个字段
               —— 前端如果要高亮具体字段，需要自己按 msg 映射
        【注意】必须 `return self`；返回新对象会丢改动
        """
        if self.password != self.confirm:
            raise ValueError("两次输入的密码不一致")
        if self.end < self.start:
            raise ValueError("结束日期不能早于开始日期")
        return self


# ============================================================
# 2. 继承：校验器会被子类继承
# ============================================================
class VipBookingCreate(BookingCreate):
    """VIP 预约：人数上限放宽到 20，其余规则原样继承。"""

    guests: int = Field(ge=1, le=20)


# ============================================================
# 3. 端点
# ============================================================
@app.post("/bookings", tags=["预约"], summary="创建预约（含校验器）")
def create_booking(payload: BookingCreate) -> dict[str, Any]:
    """【作用】响应里剔除密码字段，避免泄露

    【注意】`exclude` 是序列化参数，不改模型本身；真正的响应过滤在第 21 章
    """
    return {
        "booking": payload.model_dump(mode="json", exclude={"password", "confirm"}),
        "email_normalized": payload.email,
    }


@app.post("/vip-bookings", tags=["预约"], summary="VIP 预约（继承校验器）")
def create_vip_booking(payload: VipBookingCreate) -> dict[str, Any]:
    return {"guests": payload.guests}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
