# 06 镜像命名与拉取

## 一句话结论

镜像名是 `仓库地址/命名空间/镜像名:标签` 四段，缺省值分别是 `docker.io`、`library`、`latest`。所以 `nginx` 的完整名是 `docker.io/library/nginx:latest`。`latest` 只是默认标签名，**不代表最新**。

## 最小可运行案例

```bash
docker pull nginx:1.27-alpine          # 短名，默认 docker.io/library
docker pull docker.io/library/nginx:1.27-alpine   # 完整名，等价
docker image inspect nginx:1.27-alpine -f '{{index .RepoDigests 0}}'
```

## 怎么跑

```powershell
cd "01-镜像与容器\06-镜像命名与拉取\examples"
uv run python verify.py
```

## 镜像名四段式

```text
docker.io / library / nginx : 1.27-alpine
   │          │        │         └─ 标签（默认 latest）
   │          │        └─ 镜像名
   │          └─ 命名空间（官方镜像为 library）
   └─ 仓库地址（默认 docker.io）
```

| 写法 | 解析结果 |
| --- | --- |
| `nginx` | `docker.io/library/nginx:latest` |
| `nginx:1.27` | `docker.io/library/nginx:1.27` |
| `bitnami/nginx` | `docker.io/bitnami/nginx:latest` |
| `ghcr.io/org/app:v1` | `ghcr.io/org/app:v1` |
| `localhost:5000/app:v1` | 本地私有仓库 |

## 常见变体标签

| 标签 | 含义 | 体积参考（python:3.12） |
| --- | --- | --- |
| `3.12-slim` | 精简 Debian | 41MB |
| `3.12-alpine` | Alpine 基础 | 17MB |
| `3.12` | 完整版 | 更大 |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 生产环境版本莫名变了 | 用了 `latest` | 固定明确版本号 |
| `alpine` 里没有 bash | busybox 环境 | 用 `sh` 或装 bash |
| 拉取慢 | 国内网络 | 配镜像加速，第 05 章 |
| `manifest unknown` | 标签不存在 | `docker search` 或去 Hub 查 |
| 架构不匹配（M 芯片） | arm64 vs amd64 | `--platform linux/amd64` |
| `tag` 以为复制了镜像 | 只是别名，ID 相同 | 理解 tag 不占空间 |

## 毕业自查

- [ ] 10/10 通过
- [ ] 能把 `nginx` 还原成完整四段名
- [ ] 知道 `latest` 为什么不能用于生产
- [ ] 知道 `tag` 只是别名，不复制镜像
