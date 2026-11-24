# 33 CI/CD 与多架构构建

## 一句话结论

CI 里别写一长串 `docker build`，用 **`docker buildx bake`** 把多个镜像的构建声明化；跨架构用 **`--platform linux/amd64,linux/arm64`**，产物必须是 **manifest list**；本地缓存用 `type=local`、CI 缓存用 `type=gha`，别每次都从零编译。

## 最小可运行案例

```hcl
# docker-bake.hcl
variable "TAG" { default = "dev" }
group "default" { targets = ["api", "worker"] }

target "common" {
  context = "."
  args    = { APP_VERSION = TAG }
}

target "api" {
  inherits = ["common"]
  target   = "api"                 # 多阶段构建的某个 stage
  tags     = ["registry.example.com/app-api:${TAG}"]
}
```

```bash
docker buildx bake --print          # 先看计划
docker buildx bake --load           # 本地构建
TAG=1.4.2 docker buildx bake --push # CI 推送
```

## 怎么跑

```powershell
cd "07-生产与AI实战\33-CICD与多架构构建\examples"
uv run python verify.py
```

## 本机实测（18/18）

| 断言 | 实测 |
| --- | --- |
| `buildx version` | 可用 |
| `buildx ls` | `default` / `desktop-linux` 均 running |
| `buildx inspect --bootstrap` | `linux/amd64`、`linux/arm64`、`riscv64`、`ppc64le`、`s390x`、`arm/v7`、`arm/v6` |
| `bake --print` | 输出 JSON，target 含 `api`/`worker` |
| 变量插值 | `tags = ["ch33-api:dev"]` |
| `bake --load` | 一次构建两个镜像，内容分别为 `api` / `worker` |
| `ARG APP_VERSION` | 写入 `org.opencontainers.image.version` |
| 二次构建 | 命中本地缓存（`CACHED` > 0） |
| `--set api.tags=... --set api.args.APP_VERSION=1.2.3` | 覆盖生效，标签变 `1.2.3` |
| `--platform linux/arm64 --load` | 成功，`Architecture=arm64` |
| 多平台 + `type=oci` 导出 | 生成 tar，索引含 amd64 与 arm64 |
| `--metadata-file` | 记录产物 digest |
| `--output type=local` | `/out/hello.txt` 落到指定目录 |

## buildx 是什么

| 项 | 传统 `docker build` | `docker buildx build` |
| --- | --- | --- |
| 后端 | 内置 builder（已切 BuildKit） | 可插拔 builder（docker / docker-container / remote） |
| 多平台 | 不支持 | 支持 |
| 输出 | 只能进本地镜像库 | `image` / `local` / `oci` / `tar` / `registry` |
| 缓存导出 | 有限 | `local` / `registry` / `gha` / `s3` |
| 多目标 | 一次一个 | `bake` 一次多个 |

Docker Desktop 自带 `desktop-linux` builder（docker-container 驱动），无需额外创建。

```bash
docker buildx ls
docker buildx create --name multi --driver docker-container --use
docker buildx inspect --bootstrap
```

## bake：把构建声明化

`bake` 支持三种文件：`docker-bake.hcl`、`docker-bake.json`、`compose.yaml`（用 `x-bake`）。推荐 HCL，因为它有变量与 `inherits`。

| 概念 | 作用 |
| --- | --- |
| `target` | 一个可构建产物（镜像） |
| `group` | 一组 target 的别名（`group "default"` 是默认组） |
| `inherits` | 继承其它 target 的字段 |
| `variable` | 从环境变量或 `--set` 注入的参数 |

常用命令：

```bash
docker buildx bake --print                 # 输出最终计划（JSON），排查神器
docker buildx bake                         # 构建默认组
docker buildx bake api                     # 构建单个 target
docker buildx bake --set api.tags=x:v1     # 覆盖字段
docker buildx bake --push                  # 构建并推送
docker buildx bake --load                  # 构建并载入本地
```

## 多架构：三条路径

| 路径 | 命令 | 结果 |
| --- | --- | --- |
| 单平台交叉构建 | `--platform linux/arm64 --load` | 本地得到 arm64 镜像（本机实测可行） |
| 多平台导出 | `--platform amd64,arm64 --output type=oci,dest=out.tar` | 一个 tar 含 manifest list |
| 多平台推送 | `--platform amd64,arm64 --push` | 仓库里一个 tag 对应多个平台 |

> 实测补充：Docker Desktop（containerd 镜像存储）下多平台 `--load` 也能成功；经典 `overlay2` 存储会报 `docker exporter does not currently support exporting manifest lists`。**跨团队交付以 `--push` 或 `type=oci` 为准。**

ARM 的关键点：**如果 Dockerfile 里有 `RUN` 步骤，构建 arm64 需要 QEMU 模拟**（Docker Desktop 自带 binfmt；Linux 服务器需 `docker run --privileged --rm tonistiigi/binfmt --install all`）。模拟速度约为原生的 1/5–1/20，能用交叉编译（`GOARCH`、`--platform=$BUILDPLATFORM`）就别用模拟：

```dockerfile
FROM --platform=$BUILDPLATFORM golang:1.23 AS build
ARG TARGETOS TARGETARCH
RUN GOOS=$TARGETOS GOARCH=$TARGETARCH go build -o /app .
```

## CI 流水线骨架（GitHub Actions）

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: registry.example.com
          username: ${{ secrets.REG_USER }}
          password: ${{ secrets.REG_PASS }}
      - name: Build & push multi-arch
        run: |
          TAG=${GITHUB_SHA::7} docker buildx bake --push \
            --set "*.platform=linux/amd64,linux/arm64" \
            --set "*.cache-from=type=gha" \
            --set "*.cache-to=type=gha,mode=max"
      - name: Scan
        run: docker scout cves --only-severity critical,high --exit-code local://registry.example.com/app-api:${{ github.sha }}
```

要点：

| 要点 | 原因 |
| --- | --- |
| `setup-qemu` + `setup-buildx` | 跨架构与高级输出能力 |
| `cache-from/to=type=gha` | 跨 runner 复用层缓存 |
| tag 用 commit sha | 可追溯，避免 `latest` |
| 推送后再扫描 | 扫的是真正要发布的那个 manifest |
| `--exit-code` | 高危阻断流水线 |

## 缓存策略对比

| 类型 | 写法 | 适用 |
| --- | --- | --- |
| 本地目录 | `type=local,dest=./.buildcache` | 单机/自建 runner |
| Registry | `type=registry,ref=repo/cache` | 多 runner 共享 |
| GitHub Actions | `type=gha,mode=max` | GitHub 托管 |
| S3 | `type=s3,bucket=...` | AWS |
| inline | `type=inline` | 只能缓存镜像层，不支持 `mode=max` |

坑：**多个 target 并发写同一个本地缓存目录会冲突**（本章第一版就踩了——`bake --load` 偶发非 0 退出，但镜像其实构建成功）。解决办法是每个 target 用独立目录：

```hcl
target "api"    { cache-to = ["type=local,dest=./.buildcache/api,mode=max"] }
target "worker" { cache-to = ["type=local,dest=./.buildcache/worker,mode=max"] }
```

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `bake` 报 `could not find any target matching 'default'` | `--set` 只能改 target 字段，不能选组 | 目标写在位置参数：`bake api` |
| 多平台 `--load` 报错（经典存储） | 本地库不支持 manifest list | 用 `--push` 或 `type=oci` |
| arm64 构建卡住/极慢 | QEMU 模拟执行 `RUN` | 交叉编译或减少 `RUN` |
| 缓存不命中 | `mode=min` 或不一致的构建参数 | `mode=max`，固定 `args` |
| 并发构建互相覆盖缓存 | 共享 `dest` 目录 | 每个 target 独立目录 |
| 镜像架构不对 | 未指定 `--platform` | 显式指定 |
| CI 里 tag 是 `latest` | 没人管 | 用 sha / 语义版本 |
| `--push` 但没登录 | 缺 `docker login` | 前置登录步骤 |
| 构建慢 | 每次从零 | 配缓存 + `.dockerignore` |
| 多平台 tag 只剩一个架构 | 用了 `docker push` 而非 `buildx` | 必须用 `buildx --push` |

## 毕业自查

- [ ] 18/18 通过
- [ ] 能写出一个含 `group`/`inherits`/`variable` 的 bake 文件
- [ ] 能说出 `--load`、`--push`、`type=oci`、`type=local` 的区别
- [ ] 能解释 manifest list 与单平台镜像的关系
- [ ] 能说出 ARM 构建的两种方式（QEMU vs 交叉编译）及取舍
- [ ] 能配好 `type=gha` 缓存的 CI 步骤
- [ ] 知道多 target 共享本地缓存目录会冲突
