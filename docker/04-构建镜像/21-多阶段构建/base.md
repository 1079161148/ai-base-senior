# 21 多阶段构建 · 完整版

## 0. 怎么用

跑 10/10。本章用本机两个镜像（python-slim 作 builder、alpine 作 runtime）真实对比体积与层数。

## 1. 概念

一个 Dockerfile 可以有多个 `FROM`，每条 `FROM` 开始一个新阶段。默认只输出最后一个阶段；中间阶段只用于构建，不进最终镜像。

## 2. 机制

```text
阶段 builder:  FROM python:3.12-slim → 装工具、编译 → 产物 /build/artifact
阶段 runtime:  FROM alpine:3.20 → COPY --from=builder /build/artifact → 最终镜像
Docker 只导出最后阶段，builder 的层与工具链不进入结果
```

## 3. 逐个拆解（本机实测）

| 检查 | 单阶段 | 多阶段 |
| --- | --- | --- |
| 基础镜像 | python:3.12-slim | alpine:3.20 |
| 大小 | 41MB | 3MB |
| 层数 | 13 | 5 |
| 产物 | `built at build stage` | 同 |
| 含 python3 | 是 | 否（which 失败） |
| alpine 版本 | — | 3.20.10 |

## 4. 边界条件

- 多阶段**只是不导出**中间阶段，构建时它们仍会被执行，耗时不会减少。
- `COPY --from` 只能取文件，不能"继承"环境变量或工作目录。
- 静态编译（Go、Rust）才能真正用 `scratch`；动态链接的程序需要相符的 libc。
- `--target builder` 可以只构建到中间阶段，便于调试。
- CI 里多阶段缓存跨机器要 `--cache-from`。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 最终阶段 `COPY . .` | 源码+工具链一起进镜像 | 只拷产物 | 实测 |
| 用 scratch 跑动态链接程序 | 启动报 libc 缺失 | 用 alpine 或静态编译 | 官方 |
| 阶段名拼错 | `COPY --from` 失败 | 用 AS 统一命名 | 实测 |
| 以为多阶段会更快 | 构建时间没变 | 只减小镜像 | 实测 |
| 不清理 builder 中间文件 | 中间镜像占磁盘 | `builder prune` | 第 11 章 |
| 运行时缺配置 | 只拷了二进制 | 一并拷配置/证书 | 实测 |
| 调试时进不了容器 | 最终镜像无 shell | `--target` 调试 | 官方 |
| 多阶段+latest | 版本漂移 | 固定 tag | 第 06 章 |
| 忽略 CA 证书 | HTTPS 请求失败 | runtime 装 ca-certificates | 实测 |
| 跳过验收 | 体积没降 | 10/10 再走 | 实测 |

## 6. 最佳实践

Go/Rust 静态编译 → `scratch`；Java 用 JRE-alpine；Node 静态资源用 nginx；Python 用 slim + 虚拟环境；始终只拷产物与运行时必需文件。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Multi-stage builds |
| `[r3]` | 实测 | 10/10，41MB→3MB |

## 8. 毕业自查

- [ ] 10/10 通过
- [ ] 能为自己的项目设计多阶段 Dockerfile

## 9. 下一章

第 22 章学生产级 Dockerfile：非 root、健康检查、信号处理、固定版本。
