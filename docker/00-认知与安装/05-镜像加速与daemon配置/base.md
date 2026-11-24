# 05 镜像加速与 daemon 配置 · 完整版

## 0. 怎么用

跑 10/10。本章读取本机真实的加速配置与仓库地址，再校验一份标准 `daemon.json` 结构。

## 1. 概念

`daemon.json` 是 dockerd 的配置文件，改完重启生效。`registry-mirrors` 是 Docker Hub 的镜像代理——拉取 `docker.io` 的镜像时优先走这些地址，其它仓库（ghcr.io、私有 registry）不受影响。

## 2. 机制

```text
docker pull nginx
  → 镜像名解析为 docker.io/library/nginx:latest
  → 依次尝试 registry-mirrors 中的地址
  → 命中则加速，全部失败回源 docker.io
```

## 3. 配置项逐个拆解（本机实测）

本机实际生效的加速源：

```text
https://docker.m.daocloud.io/
https://docker.1ms.run/
https://docker.aityp.com/
```

| 字段 | 本机值 |
| --- | --- |
| `RegistryConfig.Mirrors` | 3 个 HTTPS 源 |
| `IndexServerAddress` | `https://index.docker.io/v1/` |
| `Driver` | `overlayfs` |
| 配置文件 | `%APPDATA%\Docker\settings-store.json`（8 个键） |

推荐完整配置：

```json
{
  "registry-mirrors": ["https://docker.m.daocloud.io"],
  "insecure-registries": [],
  "log-driver": "json-file",
  "log-opts": { "max-size": "50m", "max-file": "3" },
  "data-root": "/var/lib/docker",
  "live-restore": true
}
```

| 键 | 为什么重要 |
| --- | --- |
| `log-opts` | 不限制日志会让磁盘被撑爆 |
| `live-restore` | 重启 daemon 时不杀业务容器 |
| `data-root` | 数据盘单独挂载时用 |
| `insecure-registries` | 只有 HTTP 的私有仓库必须显式声明 |

## 4. 边界条件

- `registry-mirrors` 不作用于 ghcr.io / quay.io / 私有 registry。
- 云厂商加速地址（如 `xxx.mirror.aliyuncs.com`）通常仅限其云内主机。
- 公共镜像源经常停服，生产建议自建 registry 或 Harbor。
- `daemon.json` 必须是严格 JSON，注释和尾逗号都不允许。
- Docker Desktop 的配置在 GUI 里改，直接改文件可能被覆盖。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| JSON 里写注释 | daemon 启动失败 | 用纯 JSON | 官方 |
| 改完不重启 | 配置不生效 | restart docker | 实测 |
| 指望加速 ghcr.io | 依然超时 | 单独配置 | 官方 |
| 不限日志大小 | 磁盘爆满 | `log-opts` 轮转 | 最佳实践 |
| 用 `latest` 拉 | 版本不可控 | 固定 tag | 第 06 章 |
| 用云内加速地址给公网机 | 拉取失败 | 用公网源 | 官方 |
| 手改 Desktop 配置文件 | 被 GUI 覆盖 | 用 Settings | 实测 |
| 无 `live-restore` | 重启杀容器 | 开启 | 官方 |
| 不验证生效 | 以为配了 | `docker info` 查 | 实测 |
| 跳过验收 | 环境不明 | 10/10 再走 | 实测 |

## 6. 最佳实践

生产环境：自建 registry/Harbor + `log-opts` 轮转 + `live-restore`；开发机：公共加速源 + 固定镜像 tag。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | dockerd 配置参考 |
| `[r3]` | 实测 | 10/10，3 个加速源生效 |

## 8. 毕业自查

- [ ] 10/10 通过
- [ ] 能写出带日志轮转的 daemon.json

## 9. 下一章

M00 完成。第 06 章进入 M01，从镜像命名规则开始系统学镜像。
