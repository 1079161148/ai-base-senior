# 12 可写层与三种挂载

## 一句话结论

镜像层只读，容器启动时在顶部加**一层可写层**，写操作走"写时复制"。可写层随容器删除而消失，所以数据要放**卷（volume）**或**绑定挂载（bind mount）**。tmpfs 放内存，容器停止即丢。

## 最小可运行案例

```bash
# 可写层：删容器即丢
docker run --rm alpine sh -c 'echo hi > /data.txt && cat /data.txt'

# 命名卷：删容器不丢
docker volume create mydata
docker run -v mydata:/data alpine sh -c 'echo hi > /data/file'
docker run -v mydata:/data alpine cat /data/file     # 还在

# 绑定挂载：宿主可直接改
docker run -v "$(pwd)/html:/usr/share/nginx/html" nginx
```

## 怎么跑

```powershell
cd "02-数据持久化\12-可写层与三种挂载\examples"
uv run python verify.py
```

## 三种挂载对比

| 类型 | 位置 | 谁管理 | 生命周期 | 适用 |
| --- | --- | --- | --- | --- |
| volume | `/var/lib/docker/volumes/<name>/_data` | Docker | 独立于容器 | 数据库、长期数据（**推荐**） |
| bind mount | 宿主任意路径 | 你自己 | 与宿主目录同生死 | 配置、代码、日志 |
| tmpfs | 内存 | 内核 | 容器停止即消失 | 临时/敏感数据 |

## 语法对照

```bash
-v mydata:/data              # 命名卷
-v /host/path:/data          # 绑定挂载（绝对路径）
-v /host/path:/data:ro       # 只读
--tmpfs /tmp                 # 内存盘
--mount type=bind,source=/host,target=/data   # 更明确的写法
```

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `-v ./data:/data` 变成空卷 | 相对路径被当卷名 | 用绝对路径 |
| 绑定挂载后目录空了 | 挂载覆盖了镜像内原内容 | 先拷贝或换挂载点 |
| 卷名冲突 | 不同项目用了同名卷 | 加项目前缀 |
| 数据在可写层 | 删容器就丢 | 用卷 |
| SELinux 报 Permission denied | 安全标签 | 加 `:z`（第 14 章） |
| 匿名卷堆积 | `-v /data` 不带名字 | 用命名卷或 `--rm` |
| tmpfs 里放持久数据 | 停止即丢 | 改卷 |

## 毕业自查

- [ ] 11/11 通过
- [ ] 能说清三种挂载的生命周期
- [ ] 知道为什么 `-v` 要用绝对路径
- [ ] 知道 `docker diff` 只反映可写层
