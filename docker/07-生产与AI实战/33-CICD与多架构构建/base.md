# 33 CI/CD 与多架构构建 · 完整版

## 0. 怎么用

跑 18/18。本章所有结论都来自本机 BuildKit v0.31.2 + Docker 29 的真实构建，包括两次踩坑（并发写缓存目录、多平台导出结构）。

## 1. CI 里"构建"这件事的三次演进

| 阶段 | 做法 | 问题 |
| --- | --- | --- |
| 手工 | 本机 `docker build` + `push` | 不可复现、无记录 |
| 脚本化 | CI 里写多条 `docker build` | 重复配置、易漂移 |
| 声明式 | `buildx bake` + 缓存 + 多平台 | 一次定义，多产物 |

`bake` 的价值不是"少打字"，而是**构建配置进版本库、CI 与本地完全一致**。

## 2. buildx 与 builder

### 2.1 本机实测

```text
NAME/NODE        DRIVER/ENDPOINT   STATUS    BUILDKIT   PLATFORMS
default          docker            running   v0.31.2    linux/amd64 (+3), linux/arm64, ...
desktop-linux*   docker            running   v0.31.2    linux/amd64 (+3), linux/arm64, ...
```

`docker buildx inspect --bootstrap` 的 `Platforms` 字段列出全部可用平台：

```text
linux/amd64, linux/amd64/v2, linux/amd64/v3, linux/arm64,
linux/riscv64, linux/ppc64le, linux/s390x, linux/arm/v7, linux/arm/v6
```

### 2.2 三种驱动

| 驱动 | 特点 | 适用 |
| --- | --- | --- |
| `docker` | 用内置 BuildKit，镜像直接进本地库 | 日常本地构建 |
| `docker-container` | 独立容器跑 BuildKit，支持全部输出 | 多平台、cache export |
| `remote` | 连远程 BuildKit 实例 | 共享构建集群 |

```bash
docker buildx create --name ci --driver docker-container --use --bootstrap
```

## 3. bake 细节

### 3.1 本机 bake 文件

```hcl
variable "TAG" { default = "dev" }

group "default" { targets = ["api", "worker"] }

target "common" {
  context    = "."
  dockerfile = "Dockerfile"
  args       = { APP_VERSION = TAG }
  platforms  = ["linux/amd64"]
}

target "api" {
  inherits = ["common"]
  target   = "api"
  tags     = ["ch33-api:${TAG}"]
  cache-from = ["type=local,src=./.buildcache/api"]
  cache-to   = ["type=local,dest=./.buildcache/api,mode=max"]
}

target "worker" {
  inherits = ["common"]
  target   = "worker"
  tags     = ["ch33-worker:${TAG}"]
}
```

### 3.2 `--print`：先看终态再构建

```bash
docker buildx bake --print
```

输出是**插值后的最终计划**（JSON），本机实测：

```json
{
  "target": {
    "api":    { "tags": ["ch33-api:dev"],    "args": {"APP_VERSION":"dev"}, ... },
    "worker": { "tags": ["ch33-worker:dev"], ... }
  }
}
```

任何"我改了 bake 文件怎么没生效"的问题，第一步都是 `--print`。

### 3.3 `--set` 的边界（实测踩坑）

```bash
# ❌ 想通过 --set 选择默认组
docker buildx bake --set default.targets=api
# ERROR: could not find any target matching 'default'

# ✅ 目标写在位置参数
docker buildx bake api --set api.tags=x:v1 --set api.args.APP_VERSION=1.2.3
```

`--set` 只能改 **target 的字段**，不能用来选组。

实测覆盖效果：

| 操作 | 结果 |
| --- | --- |
| `--set api.tags=ch33-api:v2` | 生成本地标签 `ch33-api:v2` |
| `--set api.args.APP_VERSION=1.2.3` | 镜像标签 `org.opencontainers.image.version=1.2.3` |

## 4. 多架构构建

### 4.1 单平台交叉构建

```bash
docker buildx build --platform linux/arm64 --load -t app:arm64 --target api .
docker image inspect -f '{{.Architecture}}' app:arm64    # arm64
```

本机实测可行（Docker Desktop 自带 binfmt 与 containerd 镜像存储）。

### 4.2 多平台产物

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  --output type=oci,dest=out.tar \
  --metadata-file meta.json \
  -t app:multi --target api .
```

实测 `out.tar` 的 OCI 布局：

```text
index.json                    ← 顶层
blobs/sha256/<digest>         ← 内层 manifest list（含 amd64、arm64）
blobs/sha256/<digest>         ← 各平台 config/layers
blobs/sha256/<digest>         ← attestation（provenance/SBOM，platform=unknown）
```

解析出来的平台集合是 `{amd64, arm64, unknown}`——**多出来的 `unknown` 是 attestation**，不是镜像，这是很多人第一次看到会困惑的点。

`meta.json` 会记录产物 digest（`containerimage.digest` 等），发布时用它做审计。

### 4.3 为什么必须用 manifest list

```text
docker pull app:1.0           # 客户端按自己的架构挑一个 manifest
  → arm64 机器拿到 arm64 镜像
  → amd64 机器拿到 amd64 镜像
```

如果直接 `docker push` 单个架构的镜像，arm64 机器拉下来会跑不起来（`exec format error`）。**跨架构交付只能在 push 时用 `buildx`**。

### 4.4 QEMU vs 交叉编译

| 方式 | 原理 | 速度 | 限制 |
| --- | --- | --- | --- |
| QEMU（binfmt） | 模拟执行 arm64 指令 | 慢（1/5–1/20） | 任何 Dockerfile 都能跑 |
| 交叉编译 | 编译器直接产出目标架构二进制 | 快 | 需要语言支持（Go/Rust/C） |

Dockerfile 写法：

```dockerfile
FROM --platform=$BUILDPLATFORM golang:1.23 AS build
ARG TARGETOS TARGETARCH
WORKDIR /src
COPY . .
RUN GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o /out/app .
```

`$BUILDPLATFORM` = 构建机架构（amd64，快），`$TARGETARCH` = 目标架构（arm64）。这样 `RUN go build` 在本机原生执行，只产出不同架构的二进制——**比 QEMU 快一个数量级**。

Linux 服务器装 binfmt：

```bash
docker run --privileged --rm tonistiigi/binfmt --install all
```

## 5. 缓存

### 5.1 四种后端

| 类型 | 写法 | 共享范围 |
| --- | --- | --- |
| local | `type=local,src=./cache` | 单机目录 |
| registry | `type=registry,ref=repo/app:cache` | 任何能访问仓库的 runner |
| gha | `type=gha,mode=max` | GitHub Actions 全仓库 |
| s3 | `type=s3,bucket=b,region=r` | AWS 内网 |

`mode=min` 只导出最终层，`mode=max` 导出所有中间层（多阶段构建必需）。

### 5.2 本章实测的并发冲突

第一版把 `cache-to` 写在 `common` 里，两个 target 同时导出到 `./.buildcache`：

```text
# 现象：bake --load 偶发非 0 退出码，但镜像其实构建成功
```

原因：两个 BuildKit 进程并发写同一个本地缓存目录，`index.json` 互相覆盖/竞争。修法：**每个 target 独立目录**。

这是"看起来能用、偶发失败"的典型 CI 故障——本地跑三次都对，流水线每周挂一次。

## 6. 完整 CI 流水线

```yaml
name: build
on: { push: { branches: [main] } }
jobs:
  image:
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4

      - uses: docker/setup-qemu-action@v3        # ARM 模拟
      - uses: docker/setup-buildx-action@v3      # 多平台输出

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Bake & push
        run: |
          docker buildx bake --push \
            --set "*.platform=linux/amd64,linux/arm64" \
            --set "*.cache-from=type=gha" \
            --set "*.cache-to=type=gha,mode=max" \
            --set "TAG=${{ github.sha }}"

      - name: 扫描门禁
        run: |
          docker scout cves --only-severity critical,high \
            --exit-code local://ghcr.io/${{ github.repository }}:${{ github.sha }}

      - name: 生成 SBOM
        run: docker scout sbom ghcr.io/${{ github.repository }}:${{ github.sha }} > sbom.json
```

流水线顺序不能乱：**构建 → 推送 → 扫描（扫真产物）→ SBOM → 部署**。

## 7. 逐条验收解读（18 条）

| 组 | 覆盖内容 |
| --- | --- |
| 1–3 | buildx 可用、builder running、多平台列表 |
| 4–5 | `--print` 可解析、变量插值正确 |
| 6–9 | `bake --load` 双镜像、内容正确、OCI 标签来自 `ARG` |
| 10 | 二次构建命中本地缓存（CACHED 计数） |
| 11–12 | `--set` 覆盖 tag 与 args 并落进镜像 |
| 13–14 | arm64 单平台构建成功、架构正确 |
| 15–17 | OCI 多平台导出、索引含两平台、metadata digest |
| 18 | `type=local` 产物导出 |

## 8. 坑与对策

| 现象 | 根因 | 对策 |
| --- | --- | --- |
| `could not find any target matching` | 用 `--set` 选组 | 目标写位置参数 |
| `bake` 偶发失败但镜像在 | 多 target 共享缓存目录 | 每 target 独立目录 |
| `--load` 多平台报错 | 经典 overlay2 存储 | `--push` / `type=oci` |
| arm64 构建极慢 | QEMU 执行 RUN | 交叉编译 + `$BUILDPLATFORM` |
| 缓存永不命中 | `mode=min`、args 变化 | `mode=max`、固定构建参数 |
| `--push` 失败 | 未登录/仓库名错 | 先 `docker login`，检查 tag |
| 镜像架构不对 | 忘记 `--platform` | 显式写 |
| OCI 导出后"多一个 unknown 平台" | attestation | 正常现象 |
| CI 慢 | 无缓存 + 无并行 | `bake` 天然并行 + 缓存 |

## 9. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Docker Docs：buildx / bake / cache backends / multi-platform；GitHub Actions docker 官方 action |
| `[r3]` | 实测 | 18/18；buildx 平台列表、bake 计划、缓存命中、arm64 构建、OCI 索引结构、metadata digest 均为本机实录 |

## 10. 毕业自查

- [ ] 18/18 通过
- [ ] 能写 bake 文件的 `group`/`target`/`inherits`/`variable`
- [ ] 能解释 `--print` 的作用与 `--set` 的边界
- [ ] 能画出多平台 manifest list 的结构
- [ ] 能说明 QEMU 与交叉编译的取舍
- [ ] 能配好 `type=gha` 缓存并解释 `mode=max`
- [ ] 能说出本地缓存并发冲突的原因与修法

## 11. 下一章

第 34 章进入 AI 场景：GPU 容器、CUDA 镜像、Ollama/vLLM 推理服务、模型卷与显存限制。
