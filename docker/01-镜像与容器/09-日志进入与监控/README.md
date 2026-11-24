# 09 日志、进入容器与监控

## 一句话结论

排查容器问题有四把刀：**`logs` 看输出、`exec` 进容器、`cp` 搬文件、`stats/top` 看资源**。`exec` 是在运行中的容器里新开进程，退出不影响容器；`run -it` 退出则容器结束。

## 最小可运行案例

```bash
docker logs -f --tail 50 web          # 跟踪日志
docker exec -it web sh                # 进容器
docker cp web:/etc/nginx/nginx.conf . # 从容器拷出
docker stats --no-stream              # 资源占用快照
```

## 怎么跑

```powershell
cd "01-镜像与容器\09-日志进入与监控\examples"
uv run python verify.py
```

## 命令速查

| 命令 | 作用 | 关键参数 |
| --- | --- | --- |
| `docker logs` | 看主进程输出 | `-f` 跟踪、`--tail N`、`--since` |
| `docker exec` | 容器内执行命令 | `-it` 交互、`-u` 指定用户 |
| `docker cp` | 双向复制文件 | `宿主:容器` / `容器:宿主` |
| `docker stats` | 实时资源 | `--no-stream` 快照、`--format` |
| `docker top` | 容器内进程 | 等价宿主 `ps` 过滤 |
| `docker inspect` | JSON 详情 | `-f '{{.State.Status}}'` |
| `docker diff` | 可写层变更 | A 新增 / C 修改 / D 删除 |

## exec 与 run 的本质区别

| 对比 | `docker exec` | `docker run -it` |
| --- | --- | --- |
| 对象 | 已运行的容器 | 新容器 |
| 进程 | 新进程加入现有命名空间 | 容器主进程 |
| 退出影响 | 容器继续运行 | 容器结束 |
| 典型用途 | 排障、看配置 | 一次性交互 |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `exec` 报容器未运行 | 容器已退出 | 先 `start` 或 `run` |
| alpine 里没有 bash | busybox 环境 | 用 `sh` |
| 日志越积越大 | 未配日志轮转 | `daemon.json` 加 `log-opts`，第 05 章 |
| `docker cp` 后访问仍是旧内容 | 挂载覆盖 | 检查是否有 volume 挂载 |
| `stats` 卡住 | 默认流式输出 | 加 `--no-stream` |
| `inspect` 找不到 IPAddress | Docker 29 字段变更 | 查 `.NetworkSettings.Networks` |

## 毕业自查

- [ ] 11/11 通过
- [ ] 能说清 `exec` 与 `run -it` 的区别
- [ ] 会用 `--tail` 和 `--since` 缩小日志范围
- [ ] 知道 `docker diff` 的 A/C/D 含义
