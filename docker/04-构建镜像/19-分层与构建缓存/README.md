# 19 分层与构建缓存

## 一句话结论

每条 `RUN/COPY/ADD` 是一层，缓存按层命中：**任何一层失效，它之后的所有层都重建**。所以把"变化少的放前面、变化多的放后面"是 Dockerfile 性能的第一原则。

## 最小可运行案例

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .          # 先拷依赖清单
RUN pip install -r requirements.txt   # 依赖不变就命中缓存
COPY . .                         # 再拷代码（常变）
CMD ["python", "app.py"]
```

## 怎么跑

```powershell
cd "04-构建镜像\19-分层与构建缓存\examples"
uv run python verify.py
```

## 缓存规则

| 指令 | 缓存 key 包含 |
| --- | --- |
| `FROM` | 镜像 digest |
| `RUN` | 命令字符串 + 父层 digest |
| `COPY` | 源文件内容校验和 + 父层 digest |
| `ENV/WORKDIR/CMD` 等 | 配置值 + 父层 |

**关键：缓存是"链式"的。** 父层一变，子层全部失效。

## 本机实测（Docker 29 + BuildKit）

| 场景 | 结果 |
| --- | --- |
| 首次构建 | 0–1 个 CACHED |
| 无改动重建 | 5 个 CACHED，层列表完全相同 |
| 改 `step2.txt` | 末层 digest 变化，之前的层仍 CACHED |
| `--no-cache` | 不用缓存（仅基础镜像 resolve 显示 1 个 CACHED） |
| 构建历史 | 8 层 |
| 镜像 ID | **每次构建都不同**（BuildKit 重新生成 attestation manifest），但层可复用 |

> 重要坑：不要用镜像 ID 判断"是否命中缓存"，要看 `RootFS.Layers` 或构建日志里的 CACHED。

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 改一行代码就全量重装依赖 | `COPY . .` 在 `pip install` 之前 | 先拷依赖清单 |
| 缓存命中但代码是旧的 | 缓存了错误的层 | `--no-cache` 重建 |
| 镜像 ID 每次都变 | BuildKit attestation | 看层 digest，不看 ID |
| `RUN apt update` 单独一层 | 后续 install 用旧索引 | `apt update && apt install` 同一层 |
| 构建越来越慢 | 缓存失效或上下文太大 | `.dockerignore` |
| 多阶段构建缓存不共享 | 未用 `--cache-from` | CI 里导出/导入缓存 |

## 毕业自查

- [ ] 8/8 通过
- [ ] 能解释为什么依赖要放在代码之前
- [ ] 知道缓存是链式的
- [ ] 知道镜像 ID 变化 ≠ 缓存失效
