# 15 网络模型与默认网络 · 完整版

## 0. 怎么用

跑 11/11。本章用两个容器真实验证"同网段可通、默认 bridge 不能用容器名"。

## 1. 概念

Docker 网络本质是 Linux 网络命名空间 + veth + 网桥 + iptables 的组合。

| 驱动 | 独立 IP | 名称解析 | 出网 | 典型用途 |
| --- | --- | --- | --- | --- |
| bridge | 有 | 无（默认 bridge） | NAT | 默认 |
| host | 无（共享宿主） | — | 直接 | 高性能 |
| none | 仅 lo | 无 | 无 | 隔离 |
| 自定义 bridge | 有 | **有** | NAT | 生产单机 |

## 2. 机制

```text
创建容器 → 建一对 veth（容器内 eth0 ↔ 宿主 vethxxx）→ 把宿主端接到 docker0
→ 分配 172.17.x.x → 出网走 iptables MASQUERADE
```

## 3. 逐个拆解（本机实测）

| 检查 | 实测结果 |
| --- | --- |
| 默认网络 | `bridge`、`host`、`none` 都在 |
| bridge 网关 | `172.17.0.1` |
| 容器 IP | `172.17.0.4`（同网段） |
| 出网 | ping `223.5.5.5` 成功（约 37ms） |
| 用容器名互访 | `ping: bad address 'ch15-b'`（失败） |
| 用 IP 互访 | 成功（约 1.6ms） |
| none 网络接口数 | 1（只有 lo） |
| host 网络看到的接口 | 10 个，含 `docker0` |

## 4. 边界条件

- **默认 bridge 没有内置 DNS**，只有自定义网络才有名称解析。
- host 网络下容器没有独立 IP，"端口映射"无意义。
- none 网络连 DNS 都没有，装包会失败。
- Docker Desktop 里 docker0 在 WSL2 VM 内，Windows 宿主看不到它，但 `docker network inspect bridge` 能拿到网关。
- 容器访问宿主机服务用 `host.docker.internal`（Desktop）或网关 IP（Linux）。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 默认 bridge 里用容器名 | `bad address` | 自定义网络 | 实测 |
| 记 IP 做服务发现 | 重启后 IP 变 | 用名称 | 实测 |
| 容器里访问 `localhost:宿主端口` | 连不上 | 用网关/`host.docker.internal` | 官方 |
| host 网络做多实例 | 端口冲突 | 用 bridge + 端口映射 | 实测 |
| none 网络里 apt install | 失败 | 换 bridge | 实测 |
| 认为容器有公网 IP | 其实是 NAT 私网 | 理解 bridge | 官方 |
| 忽略 iptables | 出网失败 | 检查 NAT 规则 | 官方 |
| 生产用默认 bridge | 无 DNS、难管理 | 自定义网络 | 最佳实践 |
| 不查网络模式 | 排障无方向 | `inspect NetworkMode` | 实测 |
| 跳过验收 | 网络模型混乱 | 11/11 再走 | 实测 |

## 6. 最佳实践

生产单机一律用自定义 bridge 网络（第 16 章）；只有对网络性能极端敏感或需要绑定宿主端口时才用 host；纯计算/安全隔离任务用 none。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Docker networking |
| `[r3]` | 实测 | 11/11，容器名解析失败已实证 |

## 8. 毕业自查

- [ ] 11/11 通过
- [ ] 能解释为什么默认 bridge 不能用容器名

## 9. 下一章

第 16 章学自定义网络：给容器稳定的名字和 DNS。
