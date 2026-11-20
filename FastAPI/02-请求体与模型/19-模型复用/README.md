# 19 模型复用

## 一句话结论

复用的两个层次：**类型别名**（`Money = Annotated[Decimal, Field(gt=0)]`）跨模型共享「类型 + 约束」；**基类继承**（`StrictModel`、`ProductBase`）共享「配置 + 字段」。Create/Patch/Read 三个模型各自只声明差异，约束只写一遍。注意：PATCH 模型**不能**继承字段必填的基类。

学完这一章，你能：抽出统一的 `StrictModel`、写出 Create/Read 继承 + Patch 独立的三件套、预判子类覆盖与多继承顺序。

## 最小可运行案例

```python
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI()

Money = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
ShortText = Annotated[str, Field(min_length=1, max_length=32)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductBase(StrictModel):
    name: ShortText
    price: Money


class ProductCreate(ProductBase):
    pass


class ProductPatch(StrictModel):          # 不继承 ProductBase：字段必须可选
    name: ShortText | None = None
    price: Money | None = None


class ProductRead(ProductBase):           # 在核心字段上追加
    id: int
    created_at: datetime


@app.post("/products")
def create_product(payload: ProductCreate) -> ProductRead:
    return ProductRead(id=1, created_at=datetime.now(), **payload.model_dump())
```

完整版本（Patch、覆盖、MRO、OpenAPI 断言）见 `examples/main.py`。

## 怎么跑

```powershell
cd "02-请求体与模型\19-模型复用\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 子类继承字段 -> Create=3；Read=5；Patch=3
[PASS] 子类继承配置 -> extra_forbidden 来自继承的配置
[PASS] 别名约束复用 -> Money/Tags 别名约束在 Create 与 Patch 同时生效
[PASS] strip 来自基类 -> name='无线鼠标'
[PASS] 创建返回 Read 形态 -> id=2 price='399.00'
[PASS] Patch 复用基类配置 -> updates=["name"]，price 未变
[PASS] 继承关系 -> Create/Read ⊂ ProductBase；Patch 独立
[PASS] 子类覆盖生效，父类不变
[PASS] 多继承覆盖顺序 -> MRO 第一个父类优先
[PASS] OpenAPI 组件 -> 两个组件字段集合与 required 都不同

结果：10/10 通过
```

## 核心 API 速查

| 手段 | 写法 | 复用内容 | 适用 |
| --- | --- | --- | --- |
| 类型别名 | `Money = Annotated[Decimal, Field(...)]` | 类型 + 约束 | 跨模型重复字段 |
| 配置基类 | `class StrictModel(BaseModel): model_config = ...` | `extra`/`strip` 等 | 全项目统一 |
| 字段基类 | `class ProductBase(StrictModel): name: str` | 字段定义 | Create/Read 共享 |
| 继承 | `class ProductRead(ProductBase): id: int` | 父类字段 + 追加 | 同一资源的多个视图 |
| 组合 | `class Order(BaseModel): product: ProductRead` | 引用而不继承 | 对象嵌套（第 15 章） |

| 继承来的东西 | 是否继承 | 备注 |
| --- | --- | --- |
| 字段定义 | ✅ | 子类可重定义覆盖 |
| `model_config` | ✅ | 子类同名项覆盖父类 |
| 校验器 | ✅ | 见第 20 章 |
| 类本身 | ❌ | 父子是两个独立组件 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| PATCH 模型继承必填基类 | 字段全变必填，PATCH 不可用 | PATCH 单独继承配置基类 |
| 继承带上 `id` | 客户端能改主键 | Read 才加 `id` |
| 以为继承后是同一个 schema | OpenAPI 生成两个独立组件 | 用 `$ref` 区分 |
| 子类重定义字段却没写完整约束 | 父类的 `min_length` 丢失 | 重定义时把约束写全 |
| 多继承依赖顺序 | MRO 靠前的父类生效 | 避免多继承同名字段 |
| 用继承替代组合 | 层级越堆越深 | 嵌套用组合（第 15 章） |
| 改别名影响面没评估 | 所有用到的地方同时变 | 别名当「公共契约」对待 |

## 毕业自查

- [ ] 能说出别名与基类各自复用什么
- [ ] 能说出 PATCH 为什么不能继承必填基类
- [ ] 能预测子类重定义字段后的约束
- [ ] 能说出多继承同名字段的生效顺序
- [ ] 能看懂 OpenAPI 里两个模型为什么是两个组件
- [ ] 能判断「该用继承还是组合」
- [ ] 动手题一：给 `ProductBase` 加 `description: str | None`，观察三个模型的变化
- [ ] 动手题二：让 `ProductPatch` 继承一个「全字段可选」的基类，重写两个模型

> 想看继承与组合的取舍、MRO 细节、配置合并规则、18 条坑，继续读 [`base.md`](./base.md)。
