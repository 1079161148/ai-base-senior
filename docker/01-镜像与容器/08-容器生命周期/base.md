# 08 容器生命周期 · 完整版

## 0. 怎么用

跑 15/15。本章真实验证 SIGTERM 优雅退出（码 0）与 SIGKILL 强杀（码 137）的差异。

## 1. 概念

容器状态：`created`、`running`、`paused`、`restarting`、`exited`、`dead`、`removed`。

核心观念：**容器生命周期 = 容器内 PID 1 进程的生命周期**。主进程结束，容器就结束。

## 2. 机制

```text
docker stop
  → 向 PID 1 发 SIGTERM
  → 等待（默认 10s，可 -t 调整）
  → 仍未退出则 SIGKILL（退出码 137）

docker kill
  → 直接 SIGKILL

docker pause
  → 向所有进程发 SIGSTOP（冻结，不占 CPU）
```

## 3. 逐个拆解（本机实测）

| 操作 | 实测状态/结果 |
| --- | --- |
| `create` | `created`，未运行 |
| `start` | `running` |
| `pause` | `paused` |
| `unpause` | `running` |
| `restart` | 仍 `running` |
| `kill` | `exited`，退出码 **137** |
| `rm` | 容器消失 |
| `rm -f`（运行中） | 容器消失 |
| `stop`（进程 trap TERM） | 退出码 **0** |
| `stop -t 2`（进程忽略 TERM） | 退出码 **137** |
| `stop` 后 | 容器仍存在，`start` 后数据仍在 |

## 4. 边界条件

- `stop` 的 10 秒是默认值，`-t 0` 等于立刻 SIGKILL。
- 进程不处理 SIGTERM 会白等 10 秒，生产应实现优雅关闭。
- PID 1 若是 shell（shell 形式 CMD），信号可能传不到真正的应用进程，需 `--init` 或 exec 形式。
- `pause` 用 SIGSTOP 冻结进程，网络连接会挂起超时。
- `rm` 只删容器，不删命名卷；`rm -v` 才连匿名卷一起删。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 用 `rm` 代替 `stop` 排障 | 现场丢失 | 先 stop 再看日志 | 实测 |
| 忽略 SIGTERM | 每次停 10 秒 | 实现优雅关闭 | 实测 |
| PID 1 是 shell | 信号丢失 | exec 形式或 `--init` | 第 22 章 |
| `stop -t 0` 当常规 | 数据可能损坏 | 给足优雅时间 | 官方 |
| 认为 pause 等于 stop | 进程还在内存 | pause 是冻结 | 实测 |
| 数据写容器内 | rm 后丢失 | 用卷 | 第 12 章 |
| 反复重启不查日志 | 找不到崩溃原因 | `docker logs` | 第 09 章 |
| 强杀数据库容器 | 可能损坏 | 先 stop 优雅退出 | 最佳实践 |
| 不看退出码 | 误判成败 | 查 `State.ExitCode` | 实测 |
| 跳过验收 | 状态机混乱 | 15/15 再走 | 实测 |

## 6. 最佳实践

数据库等有状态服务必须先 `stop`（给足超时）再 `rm`；业务容器实现 SIGTERM 优雅关闭；用 `--restart` 而非手工重启。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | docker stop / kill / pause |
| `[r3]` | 实测 | 15/15，137 与 0 双路径验证 |

## 8. 毕业自查

- [ ] 15/15 通过
- [ ] 能解释为什么数据库容器不能直接 `kill`

## 9. 下一章

第 09 章学日志、进入容器、复制文件与资源监控。
