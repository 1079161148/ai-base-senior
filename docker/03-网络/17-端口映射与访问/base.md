# 17 端口映射与访问 · 完整版

## 0. 怎么用

跑 8/8。本章真实验证端口映射可访问、回环绑定、端口冲突、随机分配与多端口。

## 1. 概念

端口映射是 DNAT：改写目标地址端口，把流量从宿主转发到容器。它只影响"进入"方向，出方向靠 SNAT/MASQUERADE。

## 2. 机制

```text
docker run -p 8080:80
  → HostConfig.PortBindings: 80/tcp → 8080
  → iptables -t nat 加 DNAT 规则
  → 请求 宿主:8080 → 容器IP:80
```

Spring Boot 示例：容器内 Tomcat 默认监听 8080，所以 `-p 8080:8080`，而不是 `-p 8080:80`。

## 3. 逐个拆解（本机实测）

| 操作 | 实测结果 |
| --- | --- |
| `-p 18100:80` | HTTP 返回 `Welcome to nginx` |
| `docker port` | `80/tcp -> 0.0.0.0:18100` |
| `-p 127.0.0.1:18101:80` | 只显示 `127.0.0.1:18101`，无 `0.0.0.0` |
| 同端口再映射 | 失败：`failed to set up container networking` |
| `-P` | 自动分配宿主端口 |
| 多 `-p` | 18102、18103 同时存在 |
| `nslookup host.docker.internal` | 有 Address（Desktop 提供） |
| `inspect .NetworkSettings.Ports` | 含 18100 |

## 4. 边界条件

- 端口在 `docker run` 时确定，改映射必须重建容器。
- 默认绑 `0.0.0.0`，云主机上等于对公网开放，务必评估。
- 容器内应用必须监听 `0.0.0.0`（或 `::`），监听 `127.0.0.1` 的映射无效。
- **Docker 29 的端口冲突报错文案变了**：不再只说 `port is already allocated`，而是 `failed to set up container networking: driver failed programming external connectivity...`，本质仍是端口被占用。
- Docker Desktop 的映射由 VM 内的 docker-proxy 与宿主端口转发共同完成，与 Linux 原生 iptables 略有差异。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 应用监听 127.0.0.1 | 映射后访问不到 | 监听 0.0.0.0 | 实测 |
| 生产默认 `0.0.0.0` 暴露 | 安全风险 | 绑 127.0.0.1 或防火墙 | 安全 |
| 改 -p 不重建 | 不生效 | 删容器重建 | 官方 |
| 把错误文案当网络故障 | 排查跑偏 | 认准端口冲突 | 实测 |
| 用 EXPOSE 当映射 | 不生效 | EXPOSE 只是文档 | 第 18 章 |
| 容器内用 localhost 连宿主 | 失败 | `host.docker.internal` | 实测 |
| 多个容器抢同端口 | 启动失败 | 错开端口 | 实测 |
| UDP 忘了写 `/udp` | 只映射 TCP | 显式 `/udp` | 官方 |
| 不查 `docker port` | 不知实际映射 | 先查 | 实测 |
| 跳过验收 | 端口概念模糊 | 8/8 再走 | 实测 |

## 6. 最佳实践

生产只在反向代理层暴露 80/443，应用端口一律 `127.0.0.1` 绑定或走内网；端口规划写进文档，避免冲突。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Port publishing |
| `[r3]` | 实测 | 8/8，含 Docker 29 新错误文案 |

## 8. 毕业自查

- [ ] 8/8 通过
- [ ] 能解释 DNAT 的作用方向

## 9. 下一章

M03 完成。第 18 章进入 M04，开始自己构建镜像：Dockerfile 入门。
