# 24 本地 Registry 实战 · 完整版

## 0. 怎么用

跑 11/11。本章做一次完整的"推上去 → 删本地 → 拉回来 → 运行"闭环，不依赖任何账号。

## 1. 概念

`registry:2` 是 Docker 官方最小仓库实现，实现了 OCI Distribution Spec。它是 Harbor 的底座。

## 2. 机制

```text
docker push localhost:5000/ns/img:v1
  → POST /v2/ns/img/blobs/uploads/  上传各层
  → PUT  /v2/ns/img/manifests/v1    上传 manifest
docker pull 反之
数据落盘：/var/lib/registry/docker/registry/v2/
```

## 3. 逐个拆解（本机实测）

| 操作 | 实测 |
| --- | --- |
| `GET /v2/` | `{}` |
| `push` | 成功，digest `sha256:d9e853...` |
| `_catalog` | `{"repositories":["ch24-img"]}` |
| `tags/list` | `{"name":"ch24-img","tags":["v1"]}` |
| `rmi` 后 `pull` | 成功 |
| 运行 | `3.20.10` |
| `manifests/v1`（带 Accept） | 返回 manifest JSON |

## 4. 边界条件

- 必须挂 `/var/lib/registry`，否则容器删了镜像全丢。
- `localhost` 免 HTTPS 是 Docker 客户端的特例，换成 `192.168.x.x` 就必须配 insecure。
- 默认禁止删除 manifest，要删需 `REGISTRY_STORAGE_DELETE_ENABLED=true` 再 GC。
- Registry 没有鉴权、UI、复制、扫描，这些是 Harbor 的能力（第 25 章）。
- 存储空间只增不减，需定期 `garbage-collect`。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 不挂数据卷 | 重启丢镜像 | `-v regdata:/var/lib/registry` | 实测 |
| 非 localhost 用 HTTP | push 失败 | insecure-registries | 实测 |
| manifest 不带 Accept | 404 | 加 Accept 头 | 实测 |
| 暴露到公网 | 无鉴权风险 | 绑 127.0.0.1 或加认证 | 安全 |
| 不 GC | 磁盘涨 | `garbage-collect` | 官方 |
| 当生产仓库用 | 无 RBAC/扫描 | 用 Harbor | 第 25 章 |
| 删除不生效 | 未开删除 | 环境变量开启 | 官方 |
| 用 latest | 覆盖混乱 | 明确 tag | 第 06 章 |
| 不验证拉回 | 以为成功 | 真跑一次 | 实测 |
| 跳过验收 | 闭环没跑通 | 11/11 再走 | 实测 |

## 6. 最佳实践

内网用 Registry + 反向代理 + 认证；对外服务用 Harbor；CI 里把它当缓存仓库，减少对外网依赖。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | Distribution registry |
| `[r3]` | 实测 | 11/11，完整 push/pull 闭环 |

## 8. 毕业自查

- [ ] 11/11 通过
- [ ] 能搭本地仓库并解释数据落盘位置

## 9. 下一章

第 25 章学 Harbor：企业级仓库的 RBAC、复制、扫描与 UI。
