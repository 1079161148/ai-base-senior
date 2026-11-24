# 11 磁盘清理与系统维护

## 一句话结论

Docker 吃磁盘的三件东西是：**镜像层、停止的容器、匿名卷**。先 `docker system df` 看谁占空间，再用对应的 `prune` 精确清理。`system prune -a` 和 `rm -rf /var/lib/docker` 是两条不可逆的路，执行前必须确认。

## 最小可运行案例

```bash
docker system df                          # 先看：镜像/容器/卷/构建缓存各占多少
docker container prune -f                 # 清所有已停止容器
docker image prune -f                     # 清悬空镜像（无 tag）
docker builder prune -f                   # 清构建缓存
```

## 怎么跑

```powershell
cd "01-镜像与容器\11-磁盘清理与系统维护\examples"
uv run python verify.py
```

## 清理命令对照

| 命令 | 清理对象 | 危险度 | 说明 |
| --- | --- | --- | --- |
| `container prune` | 已停止容器 | 低 | 运行中不受影响 |
| `image prune` | 悬空镜像 | 低 | 无 tag 的中间层 |
| `image prune -a` | 所有未使用镜像 | **高** | 含带 tag 但无容器引用的 |
| `volume prune` | 未使用卷 | **高** | 卷里的数据直接没 |
| `network prune` | 未使用网络 | 低 | |
| `builder prune` | 构建缓存 | 低 | 下次构建变慢 |
| `system prune` | 容器+网络+悬空镜像+缓存 | 中 | 默认不动卷 |
| `system prune -a --volumes` | 全清 | **极高** | 等同于"重置 Docker" |

## 常用选项

| 选项 | 作用 |
| --- | --- |
| `-f` | 不交互确认（脚本用） |
| `--filter label=key=value` | 只清理带该 label 的对象 |
| `--filter until=24h` | 只清理 24 小时前的 |
| `--volumes` | system prune 时连卷一起删 |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 磁盘满但 images 看不出 | 构建缓存占大头 | `docker system df -v` 细看 |
| `prune` 后服务起不来 | 删了还在用的镜像/卷 | 先确认引用关系 |
| 卷被误删 | `system prune --volumes` | 关键数据用绑定挂载或备份 |
| 构建突然变慢 | 删了 builder 缓存 | 正常代价 |
| 日志文件撑爆磁盘 | 未配 log-opts | 第 05 章配置轮转 |
| Windows 磁盘不释放 | VM 虚拟磁盘只增不减 | Desktop 里 Reset 或重建 |
| 以为 `volume prune` 能按 label 过滤 | Docker 29 实测不生效 | 用 `volume rm` 精确删 |

## 毕业自查

- [ ] 14/14 通过
- [ ] 能按"先看 df 再 prune"的顺序操作
- [ ] 知道 `prune -a` 和 `--volumes` 的风险
- [ ] 会用 label filter 限定清理范围
