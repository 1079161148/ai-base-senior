# 32 镜像安全与供应链 · 完整版

## 0. 怎么用

跑 19/19。本章的核心实验是：**亲手构建一个"泄漏密钥"的镜像，再用 `docker history` 把它读出来**，然后改用 BuildKit `--secret` 修掉。所有断言都在本机真实执行。

## 1. 为什么镜像安全比代码安全更棘手

| 维度 | 代码仓库 | 镜像 |
| --- | --- | --- |
| 删除密钥 | 删文件 + 改历史即可（配合轮换） | **层不可变，删不掉** |
| 可见性 | 需要仓库权限 | 任何能 pull 的人都能 `history` |
| 内容清单 | 看依赖文件 | 需 SBOM 才知道装了什么 |
| 追溯 | git commit | digest + provenance attestation |

镜像 = 分层的 tar 包集合。`RUN` 的命令文本、`ARG`/`ENV` 的值、被删文件的内容（下层仍在），全部随镜像分发。

## 2. 三类泄漏与一次实测

### 2.1 反面教材

```dockerfile
FROM alpine:3.20
ARG DB_PASSWORD                 # ① 值会进历史命令文本
ENV API_TOKEN=token-written-into-image   # ② 值在镜像配置里
RUN echo "connecting with ${DB_PASSWORD}" > /tmp/build.log   # ③ 值写进层文件
```

构建：

```bash
docker build -f Dockerfile.leak -t ch32-leak:v1 \
  --build-arg DB_PASSWORD=leaked-or-not-32 .
```

### 2.2 三条泄漏路径的实测输出

| 检查 | 结果 |
| --- | --- |
| `docker history --no-trunc` | 含 `RUN /bin/sh -c echo "connecting with leaked-or-not-32"` |
| `docker inspect .Config.Env` | 含 `API_TOKEN=token-written-into-image` |
| `docker run --rm ... cat /tmp/build.log` | `connecting with leaked-or-not-32` |

即使后来加了 `RUN rm /tmp/build.log`，第 20 章讲过的道理仍成立：**上层删的是副本，下层里的数据还在**，`docker save` 出来照样能捞。

### 2.3 修复：BuildKit secret 挂载

```dockerfile
# syntax=docker/dockerfile:1
FROM alpine:3.20 AS build
RUN --mount=type=secret,id=db_password \
    test -s /run/secrets/db_password && echo "secret consumed at build time"

FROM alpine:3.20
COPY --from=build /etc/alpine-release /app/alpine-release
```

```bash
docker build --secret id=db_password,src=./secrets/db_password.txt \
  -f Dockerfile.clean -t ch32-clean:v1 .
```

实测结果：

| 检查 | 结果 |
| --- | --- |
| 构建 | 成功 |
| `docker history` 含密钥 | **否** |
| 镜像层里含密钥文件 | **否**（`/run/secrets` 只在构建期挂载） |
| `Config.Env` 含密钥 | **否** |

原理：`--mount=type=secret` 把密钥以只读 tmpfs 形式挂进**那一条 RUN** 的沙箱，命令结束即消失，不进任何层。

### 2.4 其它可选方案

| 方案 | 说明 | 适用 |
| --- | --- | --- |
| `--secret`（BuildKit） | 构建期一次性挂载 | **首选** |
| 多阶段 + 精心 COPY | 只 COPY 产物，不带源 | 编译型语言 |
| 构建时从外部注入（不碰构建） | 运行时注入配置 | 配置而非密钥 |
| 私有包仓库 + 网络鉴权 | 用仓库凭据而非镜像内密钥 | 依赖安装 |

## 3. 基础镜像与 digest

### 3.1 tag 是可变的

```bash
docker pull alpine:3.20        # 今天
docker pull alpine:3.20        # 一个月后，可能已是另一个 digest
```

tag 是"人类友好指针"，digest 才是内容哈希。

### 3.2 pin 的写法与实测

```bash
docker inspect -f '{{index .RepoDigests 0}}' alpine:3.20
# alpine@sha256:xxxx
docker pull alpine@sha256:xxxx        # 按 digest 拉取，成功
docker images --digests alpine:3.20   # 显示 digest 列
```

Dockerfile 里：

```dockerfile
FROM alpine:3.20@sha256:xxxx
```

| 收益 | 代价 |
| --- | --- |
| 构建完全可复现 | 不再自动获得补丁 |
| 防止上游 tag 被劫持/覆盖 | 需要定期重建流程 |
| 便于审计"用的是哪一版" | digest 更新要改所有 Dockerfile |

工程折中：**用版本 tag 开发，发布时 pin digest**，并配每周重建。

### 3.3 基础镜像选择

| 镜像 | 体积 | CVE 面 | 适用 |
| --- | --- | --- | --- |
| `ubuntu:24.04` | ~78MB | 大 | 需要完整系统工具 |
| `debian:12-slim` | ~75MB | 中 | 通用 |
| `alpine:3.20` | ~8MB | 小（musl 生态差异） | 轻量、Go/Rust |
| `distroless` | ~2–20MB | 最小 | 生产运行时（无 shell） |
| `scratch` | 0 | 无 | 静态二进制 |

`distroless`/`scratch` 的代价：没 shell，排障只能靠日志与 `kubectl debug`（第 36 章会讲）。

## 4. 扫描

### 4.1 本章实测的工具边界

```bash
docker scout version          # v1.23.1，可用
docker scout quickview alpine:3.20
# → Log in with your Docker ID or email address to use docker scout.
```

**结论**：scout 依赖 Docker 账号（免费），CI 里必须先 `docker login`。

### 4.2 常用门禁写法

```bash
# scout：高危即失败
docker scout cves --only-severity critical,high \
  --exit-code local://myapp:1.0

# trivy：无需账号
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed myapp:1.0
```

`--ignore-unfixed` 很实用：只报"有修复版本"的漏洞，避免被无解告警淹没。

### 4.3 扫描节奏

| 时机 | 目的 |
| --- | --- |
| 构建后（CI） | 阻断带高危的镜像进入仓库 |
| 每日/每周重扫 | 新披露的 CVE 会影响已发布镜像 |
| 上线前 | 最后一道门 |
| 事故后 | 确认影响面（配合 SBOM） |

## 5. SBOM 与签名

### 5.1 SBOM

```bash
docker buildx build --sbom=true --provenance=true -t app:1.0 --push .
docker buildx imagetools inspect app:1.0     # 看 attestation
trivy image --format spdx-json -o sbom.spdx.json app:1.0
docker scout sbom app:1.0 > sbom.json
```

SBOM 的价值在"漏洞爆发的那一刻"：Log4Shell 出现时，能立刻回答"我的 137 个镜像里哪些含 log4j-core"。

### 5.2 签名与验证

```bash
cosign generate-key-pair
cosign sign --key cosign.key registry.example.com/app@sha256:...
cosign verify --key cosign.pub registry.example.com/app@sha256:...
```

| 机制 | 回答的问题 |
| --- | --- |
| digest | 内容有没有被改 |
| SBOM | 里面有什么 |
| 签名 | 是不是我构建的、有没有被替换 |
| provenance | 用什么源、什么构建参数产出的 |

## 6. `.dockerignore`：别忘了上下文

本章实测：构建上下文里包含 `secrets/db_password.txt`，`.dockerignore` 写了 `secrets/` 后：

```bash
docker run --rm ch32-ctx:v1 cat /ctx/secrets/db_password.txt
# 不存在（BLOCKED）
docker run --rm ch32-ctx:v1 test -f /ctx/Dockerfile.ctx   # 存在
```

说明只有 `secrets/` 被排除，其它文件照常进入。必须排除的清单：

```text
.git
.env
*.pem
*.key
secrets/
node_modules/
__pycache__/
*.log
```

## 7. 逐条验收解读（19 条）

| 组 | 覆盖内容 |
| --- | --- |
| 1–2 | scout 可用、未登录时的真实行为（认证边界） |
| 3–5 | digest 存在、按 digest 拉取、`--digests` 列表 |
| 6–10 | 反面教材：ARG/ENV/RUN 三条泄漏路径全部可见 |
| 11–14 | `--secret` 构建成功，历史/层/环境变量均无明文 |
| 15–16 | 平台信息与 buildx 可用性 |
| 17–19 | `.dockerignore` 真正挡住密钥，其它文件不受影响 |

## 8. 坑与对策

| 现象 | 根因 | 对策 |
| --- | --- | --- |
| 历史里有密码 | `ARG`/`ENV` 写密钥 | `--secret` |
| 删了文件还在镜像里 | 层不可变 | 重构 Dockerfile，别在镜像里制造秘密 |
| `.env` 进了镜像 | `.dockerignore` 缺失 | 补齐排除项 |
| scout 报未登录 | 无 Docker ID | PAT + `docker login` |
| 扫描结果太多无法处置 | 没设阈值/没忽略无修复 | `--severity` + `--ignore-unfixed` |
| pin digest 后长期不更新 | 缺重建流程 | 定期重建 + 自动化 |
| 私有仓库被替换镜像 | 无签名校验 | cosign + 准入 |
| 多架构镜像 digest 不同 | manifest list | 用 manifest list 的 digest |
| 构建上下文巨大 | 把数据集/模型塞进目录 | `.dockerignore` + 外部存储 |

## 9. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Docker Docs：build secrets、`docker history`、digest 与 tag；BuildKit attestations；cosign/Trivy 文档 |
| `[r3]` | 实测 | 19/19；三条泄漏路径、`--secret` 修复效果、scout 未登录行为、`.dockerignore` 效果均为本机实录 |

## 10. 毕业自查

- [ ] 19/19 通过
- [ ] 能演示 ARG 泄漏并用 `--secret` 修复
- [ ] 能解释为什么"镜像里删文件没意义"
- [ ] 能说出 pin digest 的收益与代价
- [ ] 能写出 scout/trivy 的门禁命令
- [ ] 能说出 SBOM/digest/签名/provenance 各自的作用
- [ ] 能列出 `.dockerignore` 必排除的 8 项

## 11. 下一章

第 33 章进入 CI/CD 与多架构构建：Buildx、`buildx bake`、GitHub Actions 缓存、跨架构构建与清单合并。
