# 10 运行控制与资源限制 · 完整版

## 0. 怎么用

跑 11/11。本章真实验证"退出后自动重启 2 次"与各项配置落到 inspect 字段。

## 1. 概念

容器健壮性 = 重启策略 + 信号处理 + 资源边界 + 权限边界。默认值都不适合生产。

## 2. 机制

```text
--restart  → dockerd 监控容器退出事件，按策略重启（on-failure 记录 RestartCount）
--init     → 在容器主进程前插入 tini(PID 1)，由它转发信号并回收孤儿进程
--memory   → 写 cgroup memory.max
--cpus     → 写 cgroup cpu.max（对应 HostConfig.NanoCpus）
--user     → 修改容器内 uid/gid
```

## 3. 逐个拆解（本机实测）

| 选项 | 实测值 |
| --- | --- |
| `--restart on-failure:2` | `RestartPolicy = on-failure:2`，`RestartCount = 2` |
| `--hostname mybox` | `hostname` 输出 `mybox` |
| `--workdir /opt` | `pwd` 输出 `/opt` |
| `--user 1000:1000` | `id -u` 输出 `1000` |
| `--memory 64m` | `HostConfig.Memory = 67108864` |
| `--cpus 0.5` | `HostConfig.NanoCpus = 500000000` |
| `--init` | `HostConfig.Init = true` |
| 默认 | `HostConfig.Init` 为 `<nil>`（未设置） |
| `--entrypoint echo` | 输出 `overridden` |

## 4. 边界条件

- `--memory` 是硬限制，超了会被 OOM Killer 杀掉（退出码 137）。
- `--cpus` 是配额（quota），不是独占；多容器竞争时仍会被节流。
- `--init` 只解决 PID 1 回收问题，不解决应用自身的信号处理。
- `always` 在 daemon 重启后会把容器拉起来；`unless-stopped` 不会拉起被手动 stop 的容器。
- `--user` 需要镜像内有对应 uid，否则写文件可能失败。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 生产用默认 `no` | 崩溃后不恢复 | `unless-stopped` | 最佳实践 |
| 用 `always` 做可控服务 | 手动停不掉 | `unless-stopped` | 官方 |
| 不设内存上限 | 一个容器拖垮宿主 | `--memory` | 官方 |
| 不设 CPU 上限 | 抢占其它服务 | `--cpus` | 官方 |
| 长驻服务不加 `--init` | 僵尸进程堆积 | `--init` | 官方 |
| 默认 root 跑 | 逃逸风险 | `--user` | 第 30 章 |
| `--restart` 不设次数 | 无限重启 | `on-failure:N` | 实测 |
| 用 `--entrypoint` 覆盖掉启动脚本 | 容器起不来 | 谨慎覆盖 | 第 18 章 |
| 认为 `--cpus` 是独占 | 高负载被节流 | 用 `--cpu-shares` 调权重 | 官方 |
| 跳过验收 | 参数没生效 | 11/11 再走 | 实测 |

## 6. 最佳实践

线上标准模板：`--restart unless-stopped --init --memory --cpus --user --log-opt`，配合健康检查（第 28 章）。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | docker run 资源与重启参考 |
| `[r3]` | 实测 | 11/11，RestartCount=2 |

## 8. 毕业自查

- [ ] 11/11 通过
- [ ] 能写出线上容器标准参数模板

## 9. 下一章

第 11 章学磁盘清理：`system df`、`prune` 与空间回收。
