# 08 容器生命周期

## 一句话结论

容器有 6 个核心状态：`created → running → paused → exited → dead`，最后 `removed`。**停止（stop）不清数据，删除（rm）才丢数据**；`stop` 先发 SIGTERM 等 10 秒再 SIGKILL，`kill` 直接 SIGKILL。

## 最小可运行案例

```bash
docker create --name demo nginx     # created，不启动
docker start demo                   # running
docker pause demo                   # paused
docker unpause demo                 # running
docker stop demo                    # exited（SIGTERM→10s→SIGKILL）
docker rm demo                      # removed
```

## 怎么跑

```powershell
cd "01-镜像与容器\08-容器生命周期\examples"
uv run python verify.py
```

## 状态机

```text
            create            start              stop/kill
  镜像  ──────────►  created ────────►  running ──────────►  exited ──rm──► 消失
                                          │  ▲                 │
                                  pause   │  │ unpause          │ start
                                          ▼  │                 │
                                        paused                 └──► running
```

| 命令 | 作用 | 是否保留容器 |
| --- | --- | --- |
| `create` | 创建不启动 | 是 |
| `start` / `stop` | 启停 | 是 |
| `restart` | 重启 | 是 |
| `pause` / `unpause` | 冻结/恢复进程 | 是 |
| `kill` | 立即 SIGKILL | 是 |
| `rm` | 删除 | 否 |
| `rm -f` | 强制删除运行中的 | 否 |

## 退出码速查

| 退出码 | 含义 |
| --- | --- |
| 0 | 正常退出 / 收到 SIGTERM 后优雅退出 |
| 1 | 应用报错 |
| 137 | 128 + 9（SIGKILL） |
| 143 | 128 + 15（SIGTERM，进程未处理） |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `stop` 要等 10 秒 | 进程不响应 SIGTERM | 修应用信号处理或 `stop -t 2` |
| 数据"消失" | 执行了 `rm` 而非 `stop` | 数据放卷里，第 12 章 |
| `rm` 报容器在运行 | 未停止 | `rm -f` 或先 `stop` |
| PID 1 不是应用 | shell 形式启动 | 用 exec 形式，第 18 章 |
| `pause` 后连接超时 | 进程被冻结 | 理解 pause 是 SIGSTOP |
| 容器反复重启 | 主进程崩溃 | 看 `docker logs` |

## 毕业自查

- [ ] 15/15 通过
- [ ] 能画出容器状态机
- [ ] 知道 137 和 143 的区别
- [ ] 知道 stop 与 rm 对数据的影响
