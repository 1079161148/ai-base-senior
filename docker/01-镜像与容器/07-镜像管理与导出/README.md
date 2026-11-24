# 07 镜像管理与导出

## 一句话结论

镜像日常就五个动作：**看（images/history/inspect）、打标签（tag）、删（rmi）、导出（save）、导入（load）**。`tag` 只是别名不占空间；`rmi` 删的是 tag，最后一个 tag 删掉才真正释放；镜像被容器引用时删不掉。

## 最小可运行案例

```bash
docker images                                   # 看
docker tag alpine:3.20 myapp:v1                 # 打标签
docker save -o alpine.tar alpine:3.20           # 导出
docker load -i alpine.tar                       # 导入
docker rmi myapp:v1                             # 删标签
```

## 怎么跑

```powershell
cd "01-镜像与容器\07-镜像管理与导出\examples"
uv run python verify.py
```

## 命令速查

| 命令 | 作用 | 关键点 |
| --- | --- | --- |
| `docker images` | 列出本地镜像 | `-q` 只出 ID，`--format` 自定义 |
| `docker image inspect` | 看 JSON 详情 | `-f '{{.Size}}'` 取字段 |
| `docker history` | 看每一层怎么来的 | 排查镜像为何大 |
| `docker tag A B` | 给镜像加别名 | 不复制，ID 相同 |
| `docker rmi X` | 删镜像/标签 | 被容器占用会失败 |
| `docker save -o f.tar IMG` | 导出镜像及层 | 用于离线传输 |
| `docker load -i f.tar` | 导入镜像 | 目标是镜像，不含容器数据 |
| `docker image prune` | 清理悬空镜像 | `-a` 删所有未使用（危险） |

## save 与 export 的区别

| 命令 | 操作对象 | 是否保留层/历史 |
| --- | --- | --- |
| `docker save` | **镜像** | 保留全部层 |
| `docker export` | **容器**（文件系统快照） | 压平为一层，丢失历史 |
| `docker load` | 配合 save | 恢复镜像 |
| `docker import` | 配合 export | 得到无历史的单层镜像 |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `rmi` 提示 image is being used | 有容器在用 | 先删容器 |
| 删 tag 后镜像还在 | 还有其它 tag | 删掉所有 tag |
| `save` 出来的包很大 | 含全部层 | 正常，层无法压缩合并 |
| 用 `export` 备份 | 丢历史与元数据 | 用 `save` |
| `prune -a` 误删 | 删了所有未使用镜像 | 先 `docker images` 确认 |
| Windows 路径反斜杠 | 导出失败 | 用正斜杠或引号 |

## 毕业自查

- [ ] 12/12 通过
- [ ] 能说清 tag、digest、image ID 三者区别
- [ ] 知道 `save` 和 `export` 的适用场景
