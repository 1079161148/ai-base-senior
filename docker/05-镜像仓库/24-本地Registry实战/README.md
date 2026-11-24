# 24 本地 Registry 实战

## 一句话结论

`registry:2` 一个容器就是完整私有仓库。`localhost:端口` 默认允许 HTTP，所以不用改 daemon 配置就能 push/pull。适合内网分发、离线环境、学习和 CI 缓存。

## 最小可运行案例

```bash
docker run -d --name registry -p 5000:5000 -v regdata:/var/lib/registry registry:2
docker tag alpine:3.20 localhost:5000/alpine:v1
docker push localhost:5000/alpine:v1
docker pull localhost:5000/alpine:v1
```

## 怎么跑

```powershell
cd "05-镜像仓库\24-本地Registry实战\examples"
uv run python verify.py
```

## 本机实测闭环

| 步骤 | 结果 |
| --- | --- |
| 启动 registry（端口 18500 + 命名卷） | `/v2/` 返回 `{}` |
| `tag` 为完整仓库名 | 成功 |
| `push` | 成功 |
| `GET /v2/_catalog` | `{"repositories":["ch24-img"]}` |
| `GET /v2/ch24-img/tags/list` | `{"name":"ch24-img","tags":["v1"]}` |
| 删除本地副本 | 成功 |
| `pull` 拉回 | 成功 |
| 运行拉回的镜像 | `3.20.10` |
| 读取 manifest | 需带 `Accept` 头（见下） |

## Registry HTTP API

| 接口 | 作用 |
| --- | --- |
| `GET /v2/` | 探活，返回 `{}` |
| `GET /v2/_catalog` | 列出所有仓库 |
| `GET /v2/<name>/tags/list` | 列出标签 |
| `GET /v2/<name>/manifests/<tag>` | 读 manifest（**需 Accept 头**） |
| `DELETE /v2/<name>/manifests/<digest>` | 删镜像（需开启删除） |

```bash
# 必须指定 Accept，否则可能 404
curl -H "Accept: application/vnd.oci.image.manifest.v1+json" \
     http://localhost:5000/v2/alpine/manifests/v1
```

## 默认端口与本地特殊规则

- 容器内监听 **5000**，宿主映射随意。
- `localhost` / `127.0.0.1` 被 Docker 视为**默认允许 HTTP**，无需 `insecure-registries`。
- 其它主机名/公网 IP 用 HTTP 时必须配 `insecure-registries` 并重启 daemon。

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| push 报 HTTPS 错误 | 用了非 localhost 的 HTTP 地址 | 配 insecure-registries |
| manifest 读取 404 | 缺 Accept 头 | 加 OCI/docker manifest 头 |
| 重启后镜像没了 | 没挂 `/var/lib/registry` | 挂命名卷 |
| 删除镜像无效 | 默认不允许删除 | 启动加 `REGISTRY_STORAGE_DELETE_ENABLED=true` |
| 磁盘占满 | 无 GC | `registry garbage-collect` |
| 外网能访问 | 绑了 0.0.0.0 | 绑 `127.0.0.1:` |

## 毕业自查

- [ ] 11/11 通过
- [ ] 能独立搭一个本地仓库并完成 push/pull
- [ ] 知道 manifest 为什么需要 Accept 头
- [ ] 知道数据存在哪
