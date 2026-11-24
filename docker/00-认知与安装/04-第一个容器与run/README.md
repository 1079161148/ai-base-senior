# 04 第一个容器与 docker run

## 一句话结论

`docker run = create + start`。它的结构永远是 `docker run [选项] 镜像名 [容器内命令]`：选项决定"怎么跑"，镜像决定"跑什么环境"，镜像名后的命令**整体覆盖**镜像默认 CMD。

## 最小可运行案例

```bash
docker run --rm alpine echo hi                        # 跑完即删
docker run --rm -e NAME=docker alpine sh -c 'echo $NAME'
docker run -d --name web -p 8080:80 nginx:alpine      # 后台 + 端口映射
```

## 怎么跑

```powershell
cd "00-认知与安装\04-第一个容器与run\examples"
uv run python verify.py
```

## run 核心选项速查

| 选项 | 作用 | 常见误用 |
| --- | --- | --- |
| `-d` | 后台运行 | 前台服务用 -d 后看不到输出 |
| `-it` | 交互 + 终端 | 脚本里用 -it 会卡住 |
| `--rm` | 退出后自动删容器 | 需要保留现场时别加 |
| `--name` | 指定容器名 | 名字必须唯一 |
| `-p 宿主:容器` | 端口映射 | 只写容器端口会随机映射 |
| `-p 127.0.0.1:8080:80` | 只绑本机 | 生产要评估暴露范围 |
| `-e KEY=VALUE` | 环境变量 | 密码别用 -e（会进 inspect） |
| `-v` | 挂载 | 第 12 章详讲 |
| `--network` | 指定网络 | 第 15 章详讲 |

## run 背后发生了什么

```text
docker run
 1. 客户端联系 dockerd
 2. 本地无镜像 → 从仓库拉取
 3. 创建容器（可写层 + 网络 + 卷挂载）
 4. 启动容器主进程
 5. 前台模式把输出接到你的终端
```

## 退出码与信号

| 行为 | 结果 |
| --- | --- |
| 容器主进程 `exit 3` | `docker run` 返回 3 |
| `docker stop` | 先发 SIGTERM，10 秒后 SIGKILL |
| `docker kill` | 直接 SIGKILL |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `-d` 后容器立刻 Exited | 主进程执行完就退出 | 用长驻前台进程（如 nginx 默认） |
| 端口访问不到 | 应用监听 `127.0.0.1` | 改成监听 `0.0.0.0` |
| `--name` 冲突 | 同名容器已存在 | 先 `docker rm` 或换名 |
| `-it` 在 CI 里挂住 | 没有 TTY | CI 里别用 `-it` |
| 改了页面重启容器还在 | 数据在可写层 | 用数据卷，第 12 章 |

## 毕业自查

- [ ] 8/8 通过
- [ ] 能默写 `docker run -d --name -p -e` 的用法
- [ ] 知道 `-p 127.0.0.1:8080:80` 与 `-p 8080:80` 的区别
