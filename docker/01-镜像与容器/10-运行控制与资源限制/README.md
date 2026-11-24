# 10 运行控制与资源限制

## 一句话结论

`docker run` 的进阶选项决定"容器怎么活"：`--restart` 管自动重启、`--init` 管僵尸进程、`--user` 管权限、`--memory/--cpus` 管资源上限。线上容器的健壮性一半靠这几个参数。

## 最小可运行案例

```bash
docker run -d --name app \
  --restart unless-stopped \
  --init \
  --memory 512m --cpus 1.0 \
  --user 1000:1000 \
  myapp:1.0
```

## 怎么跑

```powershell
cd "01-镜像与容器\10-运行控制与资源限制\examples"
uv run python verify.py
```

## 重启策略

| 策略 | 行为 | 适用 |
| --- | --- | --- |
| `no`（默认） | 不自动重启 | 一次性任务 |
| `on-failure[:N]` | 非 0 退出时重启，最多 N 次 | 批处理 |
| `always` | 总是重启（含手动 stop 后 daemon 重启） | 常驻服务 |
| `unless-stopped` | 总是重启，但手动 stop 后不再拉起 | **线上推荐** |

## 关键选项速查

| 选项 | 作用 | 字段（inspect） |
| --- | --- | --- |
| `--restart` | 重启策略 | `HostConfig.RestartPolicy` |
| `--init` | 用 tini 做 PID 1，回收僵尸进程 | `HostConfig.Init` |
| `--user` | 指定运行用户 | `Config.User` |
| `--hostname` | 容器主机名 | `Config.Hostname` |
| `--workdir` | 工作目录 | `Config.WorkingDir` |
| `--memory` | 内存硬上限 | `HostConfig.Memory` |
| `--cpus` | CPU 配额 | `HostConfig.NanoCpus` |
| `--entrypoint` | 覆盖入口程序 | `Config.Entrypoint` |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 容器跑一段时间就 OOM | 内存超 `--memory` | 调大或用 `--memory-swap` |
| 容器里进程变僵尸 | PID 1 不回收 | 加 `--init` |
| 容器里写文件权限错 | 默认 root 或错误 uid | `--user` 对齐宿主 |
| `always` 后手动 stop 又自己起来 | always 会拉起 | 用 `unless-stopped` |
| `--cpus 0.5` 以为不限 | quota 生效但可被节流 | 结合 `--cpu-shares` |
| `--restart` 配错次数 | 无限重启刷日志 | `on-failure:N` 限次 |

## 毕业自查

- [ ] 11/11 通过
- [ ] 能说出 `always` 与 `unless-stopped` 的区别
- [ ] 知道 `--init` 解决什么问题
- [ ] 知道资源限制落在 cgroup
