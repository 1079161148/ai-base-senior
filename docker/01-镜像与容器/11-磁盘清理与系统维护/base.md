# 11 磁盘清理与系统维护 · 完整版

## 0. 怎么用

跑 14/14。本章用 label 过滤保证只清理本章资源，并把 Docker 29 的一个真实坑（volume prune 的 label 过滤不生效）记录下来。

## 1. 概念

Docker 占磁盘的四类对象：镜像层、容器可写层、卷、构建缓存。`system df` 分类统计，`prune` 按类回收。

## 2. 机制

```text
docker system df
  → Images / Containers / Local Volumes / Build Cache 各自 SIZE 与 RECLAIMABLE
docker xxx prune
  → 遍历对象 → 判断是否"未使用/悬空/超过 until" → 删除
```

## 3. 逐个拆解（本机实测）

| 操作 | 实测结果 |
| --- | --- |
| `system df` | 有 Images / RECLAIMABLE 列 |
| 停止容器 + `container prune --filter label=chapter=11` | 容器被删 |
| `volume create --label` + `volume prune --filter label=...` | **未被删除**（filter 不生效） |
| `volume rm` | 成功删除 |
| `network prune --filter label=...` | 网络被删 |
| `build` 后 `rmi` tag | 产生悬空镜像 |
| `image prune -f` | 成功（回收 0B 也返回 0） |
| `builder prune -f` | 成功 |
| `system prune -f --filter label=chapter=11` | 只清理带 label 的对象 |

**重要实测结论**：Docker 29 的 `volume prune --filter label=...` 不生效，必须用 `volume rm` 精确删除。而 `system prune --filter label=...` 是生效的（实测只删了带 label 的容器，无 label 的保留）。

## 4. 边界条件

- `image prune` 只删悬空（无 tag）镜像；`-a` 才删所有无容器引用的镜像。
- `system prune` 默认**不删卷**，加 `--volumes` 才删。
- `volume prune` 的 label 过滤实测无效，别在生产脚本里依赖它。
- Desktop 的虚拟磁盘（VM disk）只增不减，`prune` 后宿主空间不一定立刻释放。
- `rm -rf /var/lib/docker` 会丢掉所有镜像、容器、卷、网络，且不可恢复。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 直接 `rm -rf /var/lib/docker` | 全部丢失 | 先 prune | 官方警告 |
| 生产跑 `prune -a` | 删了在用镜像 | 加 label/until 过滤 | 实测 |
| 依赖 `volume prune --filter` | 过滤无效 | 用 `volume rm` | 实测 |
| 不看 df 就清 | 不知清什么 | 先 df | 实测 |
| 用 `--volumes` 图省事 | 数据丢失 | 单独确认 | 官方 |
| 不配日志轮转 | 日志撑爆 | log-opts | 第 05 章 |
| 以为 Desktop 磁盘会缩 | 只增不减 | Reset/重建 VM | 实测 |
| 清理运行中容器 | 服务中断 | 只清 stopped | 实测 |
| 不验证清理结果 | 以为清了 | 再 df 对比 | 实测 |
| 跳过验收 | 风险操作不熟 | 14/14 再走 | 实测 |

## 6. 最佳实践

建立例行清理：`system df` 巡检 → `container/image/builder prune`（低风险）→ 卷与镜像用 label/until 限定 → 关键数据永远有备份。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | docker system prune 参考 |
| `[r3]` | 实测 | 14/14，volume prune label 过滤失效已记录 |

## 8. 毕业自查

- [ ] 14/14 通过
- [ ] 能说出哪条清理命令最危险

## 9. 下一章

M01 完成。第 12 章进入 M02，学数据持久化：可写层与三种挂载。
