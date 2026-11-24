# 21 多阶段构建

## 一句话结论

多阶段构建让**编译环境**和**运行环境**待在两个镜像里：前面的阶段装 gcc/JDK/npm 把东西编译好，最终阶段只 `COPY --from=builder` 拿走产物。最终镜像不含编译器，体积能小一个数量级。

## 最小可运行案例

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /build
RUN echo "built at build stage" > /build/artifact.txt

FROM alpine:3.20
WORKDIR /app
COPY --from=builder /build/artifact.txt /app/artifact.txt
CMD ["cat", "/app/artifact.txt"]
```

## 怎么跑

```powershell
cd "04-构建镜像\21-多阶段构建\examples"
uv run python verify.py
```

## 本机实测对比

| 指标 | 单阶段 | 多阶段 |
| --- | --- | --- |
| 基础镜像 | python:3.12-slim | alpine:3.20 |
| 镜像大小 | **41 MB** | **3 MB** |
| 层数 | 13 | 5 |
| 最终镜像含 python | 是 | **否** |
| 产物内容 | 一致 | 一致 |

## 核心语法

| 语法 | 作用 |
| --- | --- |
| `FROM x AS builder` | 给阶段命名 |
| `COPY --from=builder /p /p` | 从指定阶段复制 |
| `COPY --from=0 /p /p` | 按序号复制 |
| `COPY --from=nginx:alpine /etc/nginx /etc/nginx` | 从任意镜像复制 |
| `--target builder` | 只构建到某阶段（调试用） |

## 典型模式

| 语言 | builder | runtime |
| --- | --- | --- |
| Go | `golang:1.22` | `scratch` / `alpine` |
| Java | `maven:3.9-eclipse-temurin-17` | `eclipse-temurin:17-jre-alpine` |
| Node | `node:20` + `npm ci && npm run build` | `nginx:alpine`（静态）或 `node:20-slim` |
| Python | `python:3.12` 编译依赖 | `python:3.12-slim` |
| Rust | `rust:1.7x` | `debian:bookworm-slim` |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 最终镜像还是很大 | 忘了只 COPY 产物 | 检查是否 `COPY . .` |
| `COPY --from` 找不到文件 | 阶段名写错或路径错 | 用 `AS` 命名并核对路径 |
| 运行时缺动态库 | 产物依赖 builder 的系统库 | 用 `-static` 或同发行版 runtime |
| 调试困难 | 最终镜像没 shell | `--target builder` 调试 |
| 构建缓存失效 | 阶段间依赖变化 | 合理排序 |
| 多阶段仍含源码 | 复制了工作目录 | 只复制产物 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能写出 Go/Java/Node 任一的多阶段 Dockerfile
- [ ] 知道 `--target` 的用途
- [ ] 知道为什么最终镜像不该含编译工具
