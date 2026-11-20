# 66 配置管理 · 完整版（base.md）

> `README.md` 给你能跑的 `Settings`；本文件把「优先级到底怎么叠、为什么必须加前缀、`SecretStr` 在哪些地方还会漏、多环境怎么组织」拆开。学完这章，你能给一个项目设计出「开发一行命令、生产零改动」的配置层。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0 / pydantic-settings 2.16.3（本机实测） |
| 前置 | 第 65 章（应用结构）、第 06 章（依赖注入） |
| 覆盖范围 | `BaseSettings`、`.env`、前缀、`SecretStr`、校验、单例 |
| 明确不覆盖 | 配置中心（Consul/etcd/Apollo）、热加载、KMS 全流程 |
| 学完验收 | 能跑通 `verify.py` 14/14、能解释 `extra` 的边界 |

## 0. 怎么用这份文件

**依据约定**：`` `[Cn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 配置从哪来、12-Factor
2 机制（第 2 节）    → 三级优先级与类型转换
3 API（第 3 节）     → SettingsConfigDict 逐个
4 边界（第 4 节）    → extra、SecretStr、嵌套、多环境
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 目录与部署
```

## 1. 概念：配置与代码分离

| 12-Factor | 做法 |
| --- | --- |
| Config | 放环境变量，不写进代码 |
| Dev/prod parity | 同一份代码 + 不同环境变量 |

```text
代码：Settings 类（声明有哪些配置、类型、默认值）
环境：APP_DATABASE_URL=...  （具体值）
```

## 2. 机制

### 2.1 优先级（实测）

```text
环境变量  >  .env 文件  >  类默认值
```

| 来源 | 实测 |
| --- | --- |
| 默认 | `dev/True/100` |
| `APP_ENV=prod, APP_DEBUG=false, APP_MAX_ITEMS=5` | `prod/False/5` |
| `.env` 里 `prod/false/7` | `prod/False/7` |
| 环境变量 9 + `.env` 7 | **9** |

### 2.2 类型转换

| 声明 | 输入 `"false"` | 结果 |
| --- | --- | --- |
| `debug: bool` | 字符串 | `False` |
| `max_items: int` | `"5"` | `5` |
| `env: Literal["dev","prod"]` | `"staging"` | `literal_error` |

### 2.3 前缀

```python
env_prefix="APP_"
```

| 变量名 | 是否生效 |
| --- | --- |
| `APP_DEBUG=false` | 是（实测 `False`）|
| `DEBUG=false` | **否**（实测仍 `True`）|

## 3. API 逐个拆解

| `SettingsConfigDict` 项 | 实测行为 |
| --- | --- |
| `env_file=".env"` | 文件不存在不报错 |
| `env_file_encoding="utf-8"` | 中文正常 |
| `env_prefix="APP_"` | 只认带前缀的 |
| `extra="forbid"` | **只**检查文件里的未知字段 |
| `case_sensitive=False` | 默认，大小写不敏感 |

### 3.1 `SecretStr`（实测）

```text
str(secret)                      → '**********'
repr(secret)                     → "SecretStr('**********')"
model_dump(mode="json")          → {'secret_key': '**********'}
secret.get_secret_value()        → 真实值
```

**结论**：可以直接把 `settings.model_dump(mode="json")` 返回给前端调试，不会泄露。

### 3.2 校验

```python
max_items: int = Field(default=100, ge=1, le=10_000)
```

| 输入 | 错误类型 |
| --- | --- |
| `0` | `greater_than_equal` |
| `20000` | `less_than_equal` |
| `abc` | `int_parsing` |

### 3.3 单例

```python
@lru_cache
def get_settings() -> Settings: ...
```

| 行为 | 结果 |
| --- | --- |
| 连续两次调用 | 同一对象 |
| 改环境后 | **仍是旧对象**，必须 `cache_clear()` |

## 4. 边界条件

### 4.1 `extra="forbid"` 的边界（实测坑）

| 来源 | 未知字段 |
| --- | --- |
| `.env` 文件 | `extra_forbidden`，loc `('app_unknown',)` |
| 环境变量 | **静默忽略** |

**原因**：系统环境里有大量无关变量，全量校验会误伤。

**对策**：拼写错误靠「启动日志打印关键配置」发现，别指望 `extra` 兜住环境变量。

### 4.2 嵌套配置

```python
class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = 5432

class Settings(BaseSettings):
    database: DatabaseSettings = DatabaseSettings()
```

环境变量用双下划线：

```text
APP_DATABASE__HOST=db.internal
```

实测未覆盖，标注为**文档约定**。

### 4.3 多环境文件

| 方案 | 说明 |
| --- | --- |
| `.env` + 环境变量 | 最简单，推荐 |
| `.env.dev` / `.env.prod` | `env_file` 按环境选 |
| `_env_file` 参数 | 测试时直接指定 |

### 4.4 测试替换

```python
app.dependency_overrides[get_settings] = lambda: Settings(debug=False)
```

比改环境变量干净。实测未覆盖，第 73 章展开。

### 4.5 多 worker

每个 worker 进程各自 `get_settings()` 一次，内存不共享。改配置必须重启。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 全局 `Settings()` | 测试无法替换 | `Depends(get_settings)` | 实测 |
| 不加前缀 | 与系统变量冲突（实测 `DEBUG` 无效）| `APP_` | 实测 |
| 明文密钥 | 日志泄露 | `SecretStr` | 实测 |
| 提交 `.env` | 密钥泄露 | `.gitignore` | `[C2]` |
| 改环境不清缓存 | 旧配置 | `cache_clear()` | 实测 |
| 期望 `extra` 管环境变量 | 静默忽略 | 启动打印配置 | 实测 |
| 直接 `os.environ` | 无校验 | `Settings` | `[C1]` |
| 用 `str` 声明枚举 | 非法值能进 | `Literal` | 实测 |
| import 时实例化 | 时序问题 | 延迟到函数 | `[C1]` |
| `bool` 写 `"yes"` | 解析异常 | `true/false` | `[C1]` |
| 生产用 dev 默认 | 泄露调试信息 | 显式设环境 | 实测 |
| 多 worker 共享内存配置 | 各自一份 | 重启生效 | 实测 |
| 热更新 | 不刷新 | 重启/清缓存 | 实测 |
| 配置里写绝对路径 | 容器里失效 | 相对/环境变量 | `[C2]` |
| 用 `Config` 类（pydantic v1 风格）| 已废弃 | `SettingsConfigDict` | `[C1]` |
| 密钥拼进 URL | 进日志 | 分开配置 | `[C2]` |
| 不写 `.env.example` | 新人不知道要配什么 | 提供样例 | `[C2]` |
| 配置项无默认值 | 启动即崩 | 给安全默认 | 实测 |
| `.env` 文件不是 UTF-8 | 中文值乱码或解析失败 | 显式 `env_file_encoding="utf-8"` | 实测 |

## 6. 最佳实践与编码建议

### 6.1 目录

```text
app/
├── config.py          # Settings + get_settings
├── main.py
├── .env.example       # 提交
└── .env               # 忽略
```

### 6.2 分环境

| 环境 | 关键项 |
| --- | --- |
| dev | `debug=true`，本地 DB |
| prod | `debug=false`，`SecretStr` 来自环境 |

### 6.3 启动自检

```python
settings = get_settings()
logger.info("env=%s debug=%s db=%s", settings.env, settings.debug, settings.database_url)
```

**不要**打印 `secret_key`：日志会被采集。

### 6.4 检查清单

| 检查项 | 原因 |
| --- | --- |
| 有 `env_prefix` | 防撞车 |
| 密钥 `SecretStr` | 防泄露 |
| `.env` 在 `.gitignore` | 防提交 |
| 有 `.env.example` | 新人可跑 |
| 枚举用 `Literal` | 早失败 |
| 数字有范围 | 防事故 |
| 端点用 `Depends` | 可替换 |
| 启动打印关键项 | 排查 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[C1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/settings/ | FastAPI 配置 |
| `[C2]` | 文档 | https://docs.pydantic.dev/latest/concepts/pydantic_settings/ | pydantic-settings |
| `[C3]` | 方法论 | https://12factor.net/zh_cn/config | 12-Factor Config |

> **核对状态**：`[C1]`–`[C3]` 为文档/方法论链接，**本次未逐页直连复核**；默认值、环境变量覆盖、`.env` 读取、环境变量优先、`SecretStr` 三处脱敏、`literal_error`、`greater_than_equal`、`.env` `extra_forbidden`（loc 小写）、环境变量未知被忽略、无前缀无效、单例、依赖注入、debug 切换、缺文件不报错均为本机实测，`examples/verify.py` 复现 14/14 通过。嵌套 `__` 分隔、`dependency_overrides` 换配置、热加载、KMS/配置中心**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 12-Factor 的配置原则
- [ ] 三级优先级的顺序
- [ ] 为什么要加前缀
- [ ] `SecretStr` 在哪些输出里脱敏
- [ ] `extra="forbid"` 的边界

**能写出（代码层）**：

- [ ] `Settings` + `SettingsConfigDict`
- [ ] `get_settings()` 单例
- [ ] `Depends(get_settings)` 注入
- [ ] 枚举与范围校验
- [ ] `.env.example`

**能判断（避坑层）**：

- [ ] 看到全局 `Settings()` → 指出不可测
- [ ] 看到明文密钥 → 指出泄露
- [ ] 看到无前缀 → 指出撞车
- [ ] 看到改环境不 `cache_clear` → 指出旧值
- [ ] 看到 `extra` 兜环境变量 → 指出无效

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `APP_ENV=prod uvicorn main:app` 后 `/health` 没有 detail
- [ ] 改 `.env` 重启看到值变化

## 9. 下一章衔接

第 67 章 `lifespan 生命周期`：`@asynccontextmanager`、启动预热、关闭清理、`yield` 的异常语义、与配置结合。

本章留下的伏笔：

1. 配置单例（66）→ 67 在 lifespan 里读配置决定预热什么。
2. `debug` 开关（66）→ 67 在关闭时决定是否清理资源。
3. 多 worker（66）→ 67 说明每个 worker 都会跑一遍 lifespan。