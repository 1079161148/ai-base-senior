# 01 容器与虚拟机 · 完整版

## 0. 怎么用

跑 12/12。这一章用真实容器验证隔离与限制，不靠背书。

## 1. 概念

| 维度 | 容器 | 虚拟机 |
| --- | --- | --- |
| 隔离对象 | 进程 | 整台硬件 |
| 是否含内核 | 共用宿主机内核 | 每个 VM 一个完整 Guest OS |
| 启动速度 | 秒级 | 几十秒到分钟 |
| 体积 | 几十到几百 MB | 几 GB |
| 资源开销 | 低 | 高 |
| 隔离强度 | 较弱 | 强 |

容器与 VM 不是替代关系：VMware + Rocky Linux + Docker 层层嵌套是常见实验环境。

## 2. 机制

```text
docker run
  → runc 创建新进程
  → 挂上 namespace（pid/net/mnt/uts/ipc/user）
  → 写入 cgroup 限额（cpu/memory）
  → 用 OverlayFS 拼出根文件系统（lower 只读层 + upper 可写层）
  → execve 容器主进程，PID 在容器内是 1
```

## 3. 三大技术逐个拆解

| 技术 | 作用 | 本机实测值 |
| --- | --- | --- |
| namespace | 隔离视图 | `/proc/1/ns` 含 `pid net mnt uts cgroup ipc user time` |
| cgroups | 限制资源 | `--memory 64m` → `memory.max=67108864` |
| OverlayFS | 分层文件系统 | `Storage Driver: overlayfs`（Docker 29） |

CPU 限制：`--cpus 0.5` 落到 `HostConfig.NanoCpus = 500000000`。

## 4. 边界条件

- Linux 容器只能跑 Linux 内核；Windows/macOS 的 Docker Desktop 运行一个小 Linux VM（WSL2 或 HyperKit），容器实际跑在 VM 里。
- 本机实测内核串为 `6.18.40.1-microsoft-standard-WSL2`，正是这一点的证据。
- cgroup v2 与 v1 路径不同：v2 是 `/sys/fs/cgroup/memory.max`，v1 是 `/sys/fs/cgroup/memory/memory.limit_in_bytes`。
- namespace 隔离不等于安全隔离，容器逃逸仍是真实攻击面。

## 5. 注意事项对照表

| 错误做法 / 认知 | 现象 / 后果 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 认为容器有独立内核 | 无法解释 `uname -r` 与宿主一致 | 记住共用内核 | 实测 |
| 用容器做强隔离 | 逃逸风险 | 强隔离用 VM/gVisor | 官方 |
| cgroup 路径写死 v1 | v2 环境读不到 | 两种路径兼容 | 实测 |
| 认为 `--memory` 只是软限制 | 被 OOM 杀 | 它是硬限制 | 实测 |
| 容器内 `localhost` 当宿主 | 连接失败 | 用服务名或宿主 IP | 第 15 章 |
| 认为 Desktop 等于 Windows 容器 | 拉 Linux 镜像能跑但概念错 | 区分 Linux/Windows 容器 | 官方 |
| 忽略 `--cpus` 也会被 quota 限制 | CPU 被节流 | 用 `--cpu-shares` 调权重 | 实测 |
| 不看存储驱动 | 排障无方向 | `docker info` 先看 Driver | 实测 |
| 跳过 `--init` | 僵尸进程 | 长驻服务加 `--init` | 第 22 章 |
| 跳过验收 | 直觉错误 | 12/12 再走 | 实测 |

## 6. 最佳实践

把"容器是进程"刻进脑子里：所有关于进程的知识（信号、PID 1、文件描述符、退出码）都适用于容器。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Docker 官方 Architecture / Security |
| `[r3]` | 实测 | 12/12，WSL2 内核 + overlayfs |

## 8. 毕业自查

- [ ] 12/12 通过
- [ ] 能解释 `--memory` 和 `--cpus` 落到哪里
- [ ] 知道 cgroup v1/v2 路径差异

## 9. 下一章

第 02 章装 Docker：Windows / macOS / Linux 三平台完整步骤。
