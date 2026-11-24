# 03 Docker Desktop 桌面端 · 完整版

## 0. 怎么用

跑 13/13。本章验收读取本机真实的 Desktop 配置与资源分配，不是静态文字检查。

## 1. 概念

Docker Desktop 是面向 Windows/macOS（以及 Linux 桌面）的一体化应用，包含：

| 组成 | 作用 |
| --- | --- |
| Linux VM（WSL2/HyperKit/QEMU） | 真正跑容器的环境 |
| dockerd + containerd + runc | 容器引擎 |
| docker CLI | 命令行 |
| Compose / Buildx 插件 | 编排与构建 |
| Kubernetes（可选） | 本地单节点集群 |
| GUI Dashboard | 图形化管理 |
| Extensions | 扩展生态 |

## 2. 机制

```text
Windows/macOS 宿主
  └─ Docker Desktop 应用
       └─ Linux VM（WSL2 等）
            └─ dockerd → containerd → runc → 容器
```

`docker context` 把本机指向 Desktop 提供的 endpoint，所以你在 PowerShell 里敲的命令，实际发给了 VM 里的 dockerd。

## 3. 关键项拆解（本机实测）

| 项 | 本机值 |
| --- | --- |
| OperatingSystem | `Docker Desktop (containerized)` |
| context | `desktop-linux` |
| NCPU | 20 |
| MemTotal | 15.5 GB |
| DockerRootDir | `/var/lib/docker` |
| Desktop CLI | `v0.4.3` |
| 配置文件 | `%APPDATA%\Docker\settings-store.json` |

配置文件里的关键开关：

| 键 | 含义 |
| --- | --- |
| `AutoStart` | 开机自启 |
| `EnableDockerAI` | Docker AI 功能开关 |
| `UseContainerdSnapshotter` | 使用 containerd 镜像存储 |
| `InferenceCanUseGPUVariant` | 推理是否可用 GPU 变体 |
| `SettingsVersion` | 配置版本 |

## 4. 边界条件

- Desktop 的磁盘、CPU、内存上限独立于宿主，调小了会 OOM 或磁盘满。
- 商用许可：大型企业使用 Docker Desktop 需付费订阅。
- Windows 家庭版只能用 WSL2 后端。
- GUI 与 CLI 操作同一份引擎状态，二者等价。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 改 Resources 不 Apply | 不生效 | Apply & Restart | 官方 |
| 把 VM 路径当宿主路径 | 找不到文件 | 用 bind mount | 第 12 章 |
| 磁盘不清理 | 构建失败 | `docker system df`+prune | 第 11 章 |
| 默认不开 GPU 却跑 CUDA | 报 no CUDA device | 开启 GPU 支持 | 第 32 章 |
| 在生产机装 Desktop | 许可与稳定性问题 | 用 Engine | 官方 |
| 随意切 context | 命令打到别处 | `docker context show` 确认 | 实测 |
| 不看 settings-store.json | 配置来源不清 | 可读可审计 | 实测 |
| 用 GUI 删卷不确认 | 数据丢失 | 先 `docker volume ls` | 第 12 章 |
| 跳过验收 | 环境不明 | 13/13 再走 | 实测 |

## 6. 最佳实践

开发机：Desktop + 合理资源 + 镜像加速；服务器：Engine + systemd + 固定版本。日常养成 `docker system df` 看空间的习惯。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | 官方 | Docker Desktop 文档 |
| `[r2]` | 实测 | 13/13，读取 settings-store.json |

## 8. 毕业自查

- [ ] 13/13 通过
- [ ] 能说出 Desktop 与 Engine 的适用场景

## 9. 下一章

第 04 章跑第一个容器，并一次性看清 `docker run` 的所有核心选项。
