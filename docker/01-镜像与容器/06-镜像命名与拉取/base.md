# 06 镜像命名与拉取 · 完整版

## 0. 怎么用

跑 10/10。本章把镜像名规则、digest、tag 别名、变体、平台一次性讲透。

## 1. 概念

| 术语 | 定义 |
| --- | --- |
| Registry | 仓库服务，如 docker.io、ghcr.io |
| Repository | 仓库内的一个镜像名，如 `library/nginx` |
| Tag | 版本标签，如 `1.27-alpine` |
| Digest | 内容哈希 `sha256:...`，唯一标识镜像内容 |
| Image ID | 本地镜像 ID，也是 sha256 |

## 2. 机制

```text
镜像名 → 补全默认值 → 访问 registry /v2/<name>/manifests/<tag>
       → 拿 manifest（含 config + layers 的 digest 列表）
       → 按层去重下载 → 本地组装
```

关键：**tag 可以被重新指向另一个 digest**，所以同名 tag 在不同时间拉到的内容可能不同；digest 才是不可变的。

## 3. 逐个拆解（本机实测）

| 操作 | 实测结果 |
| --- | --- |
| `pull nginx:1.27-alpine` | 成功，短名可用 |
| `inspect docker.io/library/nginx:1.27-alpine` | 与短名等价 |
| `RepoDigests` | `nginx@sha256:65645c7b...` |
| `pull alpine` | 得到 `alpine:latest` |
| `alpine:3.20` vs `latest` digest | 不同 |
| `tag alpine:3.20 ch06-alias:v1` | 两者 ID 完全相同 |
| `python:3.12-alpine` vs `slim` | 17MB vs 41MB |
| `Architecture` | `amd64` |

## 4. 边界条件

- `latest` 只是默认标签，可能指向旧版本；生产必须固定版本号。
- tag 可被覆盖，digest 不可变；需要严格复现时用 `image@sha256:...`。
- 跨架构镜像需要 `--platform`；Apple Silicon 拉 amd64 镜像会走模拟，慢且可能崩。
- 私有仓库必须带完整地址（含端口）。
- Alpine 基于 musl libc，某些二进制（glibc 编译）跑不起来。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 生产用 latest | 版本漂移 | 固定 tag 或 digest | 官方 |
| 认为 tag 复制镜像 | 磁盘没变 | 理解别名 | 实测 |
| 用 digest 当 tag 名 | 语法错 | `name@sha256:...` | 官方 |
| M 芯片不指定平台 | 运行慢/崩 | `--platform` | 实测 |
| 私有仓库不带端口 | 解析失败 | 写全 `host:port` | 第 23 章 |
| Alpine 里用 bash | command not found | 用 sh | 实测 |
| 只记短名 | 换 registry 时出错 | 心里有完整四段 | 实测 |
| 不看 Architecture | 架构不符 | `inspect` 先确认 | 实测 |
| 不验证 digest | 无法复现 | 记录 digest | 最佳实践 |
| 跳过验收 | 命名规则不清 | 10/10 再走 | 实测 |

## 6. 最佳实践

生产镜像用「明确版本 tag + 记录 digest」双保险；基础镜像优先 `alpine`/`slim`，但注意 musl 兼容性。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Docker 镜像规范 |
| `[r3]` | 实测 | 10/10，含 digest 与体积对比 |

## 8. 毕业自查

- [ ] 10/10 通过
- [ ] 能解释 tag 与 digest 的区别

## 9. 下一章

第 07 章系统学镜像管理：查看、打标签、导出、导入、看层历史。
