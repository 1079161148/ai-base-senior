# 09 日志、进入容器与监控 · 完整版

## 0. 怎么用

跑 11/11。本章用一个真实 nginx 容器完成日志、exec、cp、stats、top、diff 全流程。

## 1. 概念

| 能力 | 命令 | 数据来源 |
| --- | --- | --- |
| 日志 | `docker logs` | 主进程 stdout/stderr（由 log-driver 收集） |
| 进容器 | `docker exec` | 在已有 namespace 里 fork 新进程 |
| 搬文件 | `docker cp` | 直接在宿主机与容器文件系统间拷贝 |
| 资源 | `docker stats` | cgroup 统计 |
| 进程 | `docker top` | 宿主 ps 视角看容器进程 |
| 变更 | `docker diff` | OverlayFS 可写层差异 |

## 2. 机制

```text
logs：容器主进程 stdout/stderr → log-driver(json-file) → /var/lib/docker/containers/<id>/<id>-json.log
exec：docker exec → 在容器已有 pid/net/mnt namespace 里 exec 新进程
cp  ：docker cp → 通过 dockerd 在宿主与容器 rootfs 之间读写
```

## 3. 逐个拆解（本机实测）

| 操作 | 实测结果 |
| --- | --- |
| `logs` | 有 nginx 启动输出 |
| `logs --tail 2` | 1 行 |
| `exec nginx -v` | 返回码 0（输出走 stderr） |
| `exec` 后容器状态 | 仍 running |
| `cp` 宿主→容器 | 访问 `/hello.txt` 得到 `hello-cp` |
| `cp` 容器→宿主 | 拿到 644 字节的 nginx.conf |
| `stats --no-stream` | `ch09-web 0.00%` |
| `top` | 表头 UID PID PPID |
| `inspect` 取 IP | 172.x.x.x |
| `diff` | 出现 `/tmp/newfile` |

## 4. 边界条件

- `docker logs` 只能看到容器**主进程**的输出，多进程容器里其它进程的日志默认看不到。
- 日志由 log-driver 决定位置与轮转；`json-file` 不限大小会撑爆磁盘。
- `docker diff` 只反映可写层，挂载卷的变化不在里面。
- `exec` 需要容器内有对应可执行文件（alpine 没有 bash）。
- Docker 29 起 `NetworkSettings.IPAddress` 顶层字段移除，要从 `Networks` 里取。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 不做日志轮转 | 磁盘爆满 | `log-opts` max-size | 第 05 章 |
| `exec` 进已停容器 | 报错 | 先 start | 实测 |
| 用 bash 进 alpine | command not found | 用 sh | 实测 |
| 在容器里改配置 | 重启即丢 | 用挂载 | 第 12 章 |
| `stats` 不加 `--no-stream` | 卡住 | 加参数 | 实测 |
| 用 inspect 顶层 IP | 字段不存在 | 查 Networks | 实测 |
| 认为 diff 能看到卷 | 看不到 | diff 只看可写层 | 实测 |
| 只 tail 不看时间 | 定位不准 | `--since 10m` | 官方 |
| 用 cp 改代码 | 不持久 | 用 volume | 第 12 章 |
| 跳过验收 | 排障手段缺失 | 11/11 再走 | 实测 |

## 6. 最佳实践

生产必配日志轮转；排障顺序固定为「`ps -a` 看状态 → `logs` 看报错 → `inspect` 看配置 → `exec` 进容器验证」。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | docker logs / exec / cp / stats |
| `[r3]` | 实测 | 11/11，含 Docker 29 字段变更适配 |

## 8. 毕业自查

- [ ] 11/11 通过
- [ ] 能默写排障四步顺序

## 9. 下一章

第 10 章学运行控制：重启策略、`--init`、用户、资源限制。
