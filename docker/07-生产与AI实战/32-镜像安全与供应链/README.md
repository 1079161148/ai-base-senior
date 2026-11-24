# 32 镜像安全与供应链

## 一句话结论

镜像一旦构建，里面的东西**删不掉**：`ARG`/`ENV` 的值会永久留在镜像历史与配置里，任何能 `docker pull` 的人都能读出来。正确做法是 **BuildKit `--secret` 挂载 + digest 固定 + 扫描门禁 + 签名**。

## 最小可运行案例

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS build
RUN --mount=type=secret,id=pip_token \
    pip install --extra-index-url "https://token:$(cat /run/secrets/pip_token)@pkg.example.com/simple" -r requirements.txt
```

```bash
docker build --secret id=pip_token,src=$HOME/.pip_token -t app:1.0 .
```

## 怎么跑

```powershell
cd "07-生产与AI实战\32-镜像安全与供应链\examples"
uv run python verify.py
```

## 本机实测（19/19）

| 断言 | 实测 |
| --- | --- |
| `docker scout version` | v1.23.1 可用 |
| 未登录直接 `scout quickview` | 提示 `Log in with your Docker ID`（CI 需 PAT） |
| `RepoDigests` | `alpine@sha256:...` |
| 按 digest 拉取 | 成功 |
| `images --digests` | 列出 digest |
| 反面教材：`ARG DB_PASSWORD` | **镜像历史里出现明文密码** |
| `ENV API_TOKEN=...` | 出现在 `Config.Env` |
| `RUN echo $DB_PASSWORD > /tmp/build.log` | 值留在镜像文件系统里 |
| `--secret` 构建 | 成功 |
| secret 是否进历史 | **否** |
| secret 是否进层/环境变量 | 否 / 否 |
| `.dockerignore` | `secrets/` 未进构建上下文，其它文件正常进入 |
| `buildx version` | BuildKit 可用 |

## 供应链的五个环节

```text
① 构建入口   基础镜像是否可信、是否 pin digest
② 构建过程   密钥是否泄漏（ARG/ENV/层）、是否最小化
③ 产物       漏洞扫描、SBOM、签名
④ 分发       仓库鉴权、复制、保留策略
⑤ 运行       准入策略、只跑 digest、定期重扫
```

## ① 基础镜像：pin digest

| 写法 | 可复现性 | 风险 |
| --- | --- | --- |
| `FROM python:3` | 最差 | 大版本漂移 |
| `FROM python:3.12-slim` | 中 | 小版本/补丁漂移 |
| `FROM python:3.12-slim@sha256:...` | **最高** | 需手动更新 |

```dockerfile
FROM python:3.12-slim@sha256:af4e85b3cf3c8f0d1f0e3a0f1c... 
```

取 digest：

```bash
docker buildx imagetools inspect python:3.12-slim | Select-String Digest
docker inspect -f '{{index .RepoDigests 0}}' python:3.12-slim
```

权衡：pin digest 后安全补丁不会自动进来，必须有**定期重建**流程（每周/每月），否则等于锁死一个旧漏洞。

## ② 构建期密钥：三种写法对比

| 写法 | 是否进历史 | 是否进镜像 | 结论 |
| --- | --- | --- | --- |
| `ARG DB_PASSWORD` | **是**（命令文本） | 是 | 禁止 |
| `ENV API_TOKEN=...` | 是 | 是 | 禁止 |
| `COPY .env /app/` | 否 | **是** | 禁止 |
| `RUN --mount=type=secret` | 否 | 否 | **推荐** |
| 多阶段：密钥只在前一阶段用 | 否 | 否（不 COPY 产物外的东西） | 可用但需谨慎 |

本章实测到的"泄漏长什么样"：

```bash
docker history --no-trunc ch32-leak:v1
# RUN /bin/sh -c echo "connecting with leaked-or-not-32" ...   ← 明文
docker inspect -f '{{json .Config.Env}}' ch32-leak:v1
# ["API_TOKEN=token-written-into-image", ...]
docker run --rm ch32-leak:v1 cat /tmp/build.log
# connecting with leaked-or-not-32
```

三条泄漏路径全部可见，而且**在镜像里删不掉**（层不可变，第 20 章的"幽灵数据"）。

## ③ 扫描：工具与门禁

| 工具 | 特点 | 用法 |
| --- | --- | --- |
| `docker scout` | Docker 官方，Desktop 内置 | `docker scout cves <img>` |
| `trivy` | 开源、覆盖率好、可扫文件系统/配置 | `trivy image <img>` |
| `grype` | Anchore，SBOM 驱动 | `grype <img>` |
| `snyk` | 商业，IDE 集成好 | `snyk container test <img>` |

本章实测的边界：**scout 需要登录**（Docker ID / PAT），未登录时直接提示登录。CI 里的写法：

```bash
echo "$DOCKER_PAT" | docker login -u "$DOCKER_USER" --password-stdin
docker scout cves --only-severity critical,high --exit-code local://myapp:1.0
```

`--exit-code` 是门禁的关键：有高危就返回非 0，流水线直接失败。

trivy 示例（不需要账号）：

```bash
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image --severity HIGH,CRITICAL --exit-code 1 myapp:1.0
```

扫描策略建议：

| 严重级别 | 处理 |
| --- | --- |
| CRITICAL | 阻断发布，24h 内修 |
| HIGH | 阻断发布，7 天内修 |
| MEDIUM | 记录 + 排期 |
| LOW | 忽略（噪音） |
| 无修复版本 | 记录风险，评估隔离措施 |

## ④ SBOM 与签名

```bash
# 生成 SBOM（BuildKit attestation）
docker buildx build --sbom=true --provenance=true -t app:1.0 --push .
docker buildx imagetools inspect app:1.0        # 能看到 attestation

# 或独立工具
docker scout sbom app:1.0 > sbom.json
trivy image --format spdx-json -o sbom.json app:1.0
```

签名（cosign）：

```bash
cosign generate-key-pair
cosign sign --key cosign.key registry.example.com/app@sha256:...
cosign verify --key cosign.pub registry.example.com/app@sha256:...
```

签名解决"这个镜像是不是我构建的"，digest 解决"内容有没有变"，SBOM 解决"里面有什么"。三者组合才是完整的供应链证据链。

## ⑤ 运行期准入

| 策略 | 实现 |
| --- | --- |
| 只允许 digest 或受信仓库 | K8s admission policy / OPA Gatekeeper |
| 禁止 `latest` | CI 检查 tag |
| 禁止 root | `runAsNonRoot`（第 30 章） |
| 禁止 `--privileged` | 编排平台策略 |
| 定期重扫 | 每周 cron 扫一遍已部署镜像 |

## 常用命令

```bash
docker scout quickview <img>
docker scout cves --only-severity critical <img>
docker scout recommendations <img>      # 升级基础镜像建议
docker scout compare --to <旧镜像> <新镜像>
docker history --no-trunc <img>          # 手工查泄漏最快的方式
docker inspect -f '{{json .Config.Env}}' <img>
docker inspect -f '{{index .RepoDigests 0}}' <img>
docker buildx imagetools inspect <img>   # 多架构 manifest 与 digest
```

**上线前必做的两个手工检查**（比任何扫描都快）：

```bash
docker history --no-trunc <img> | Select-String -Pattern "password|token|secret|key"
docker run --rm <img> env | Select-String -Pattern "password|token|secret|key"
```

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 密码出现在镜像里 | 用了 `ARG`/`ENV`/`COPY` | 改 `--secret` |
| 镜像里有 `.env` / `.git` | `.dockerignore` 没配 | 补齐排除项 |
| 扫描结果全是 LOW | 没设阈值 | `--severity HIGH,CRITICAL` |
| CI 扫描失败 | scout 未登录 | PAT + `docker login` |
| 扫出来的漏洞修不了 | 基础镜像太旧 | 换 slim/alpine/distroless + 定期重建 |
| 用了 `latest` | 无法追溯 | 用版本 tag + digest |
| digest 写死后再也不更新 | 没有重建流程 | 每周重建 + 自动 PR |
| 私有仓库镜像被替换 | 无签名校验 | cosign + 准入策略 |
| SBOM 生成了没人看 | 无流程 | 存进制品库，漏洞爆发时检索 |

## 毕业自查

- [ ] 19/19 通过
- [ ] 能说出三条密钥泄漏路径，并演示其中一条
- [ ] 能写出 `--secret` 的正确用法（Dockerfile + build 命令）
- [ ] 能解释 digest 与 tag 的区别，以及 pin digest 的代价
- [ ] 能说出 SBOM/digest/签名各自解决什么问题
- [ ] 知道 scout 未登录时的行为与 CI 里的处理
- [ ] 能配一个"高危阻断"的扫描门禁
