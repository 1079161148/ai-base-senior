# 07 镜像管理与导出 · 完整版

## 0. 怎么用

跑 12/12。本章用 `commit` 造一个单 tag 镜像，真实验证"被占用不能删"。

## 1. 概念

| 术语 | 说明 |
| --- | --- |
| Image ID | 本地镜像内容的 sha256，多 tag 可共享 |
| Tag | `repo:tag` 形式的可读别名，可被覆盖 |
| 悬空镜像 | 没有 tag 指向的中间层，`<none>:<none>` |

## 2. 机制

```text
tag A B        → 新增一条 tag 记录，指向同一 image ID（不复制字节）
rmi B          → 删 tag 记录；若还有其它 tag 指向该 ID，镜像保留
rmi <最后一个 tag> → 删除 image ID 记录；若无容器引用，层数据才由 GC 回收
```

## 3. 逐个拆解（本机实测）

| 操作 | 实测结果 |
| --- | --- |
| `tag alpine:3.20 ch07-alias:v1` | 两者 ID 完全相同 |
| `history` | alpine 有 2 层 |
| `inspect -f {{.Size}}` | 3555 KB |
| `save -o alpine.tar` | 3644 KB |
| `load -i alpine.tar` | `Loaded image: alpine:3.20` |
| 容器占用时 `rmi` | 非零退出，提示 image is being used |
| 删容器后 `rmi` | 成功 |
| `image prune -f` | 可执行 |

## 4. 边界条件

- **多 tag 共享 ID 时，`rmi` 只 untag，不删数据。** 这是最容易误判"为什么删不掉/为什么还能用"的地方。
- `rmi -f <image ID>` 会删除该 ID 的**所有** tag，慎用。
- `save` 保存镜像（含层与历史），`export` 保存容器文件系统（压平，丢历史）。
- 镜像被任何容器（含已停止）引用时都不能删。
- `prune -a` 会删除所有"未被容器使用"的镜像，生产慎用。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 用 ID 批量删 | 其它 tag 一起没了 | 用 `repo:tag` 删 | 实测 |
| 用 export 备份镜像 | 丢历史 | 用 save | 官方 |
| 认为 tag 复制镜像 | 磁盘不变 | tag 是别名 | 实测 |
| 删不掉就强删 | 可能误伤 | 先清容器 | 实测 |
| `prune -a` 不确认 | 镜像全没 | 先 `images` 核对 | 最佳实践 |
| 只删 tag 就以为释放空间 | 空间未回收 | 删完所有 tag | 实测 |
| 用 latest 导出 | 复现困难 | 导出带版本 tag | 第 06 章 |
| 不清理悬空镜像 | 磁盘涨 | 定期 prune | 第 11 章 |
| 忽略 history | 不知镜像为何大 | 用 history 定位 | 第 20 章 |
| 跳过验收 | 概念混淆 | 12/12 再走 | 实测 |

## 6. 最佳实践

离线交付用 `save/load`；线上清理用「先 stop/rm 容器 → 再 rmi → 再 prune」三步；禁止在脚本里用 `rmi -f <ID>`。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | docker image / save / load |
| `[r3]` | 实测 | 12/12，commit 单 tag 镜像验证占用 |

## 8. 毕业自查

- [ ] 12/12 通过
- [ ] 能解释多 tag 共享 ID 时 `rmi` 的行为

## 9. 下一章

第 08 章学容器生命周期：create / start / stop / restart / kill / rm。
