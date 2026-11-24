# 18 Dockerfile 入门与常用指令

## 一句话结论

Dockerfile 是一份"从基础镜像开始，按顺序执行指令"的构建脚本：每条 `RUN/COPY/ADD` 产生一层，`ENV/WORKDIR/EXPOSE/USER/CMD/ENTRYPOINT` 只写配置。**CMD 给默认参数，ENTRYPOINT 定入口程序**，命令行参数会覆盖 CMD 而不是 ENTRYPOINT。

## 最小可运行案例

```dockerfile
FROM python:3.12-slim
WORKDIR /www
COPY index.html .
COPY app.py .
EXPOSE 8000
CMD ["python", "app.py"]
```

```bash
docker build -t myweb:1.0 .
docker run -d -p 8080:8000 myweb:1.0
```

## 怎么跑

```powershell
cd "04-构建镜像\18-Dockerfile入门与常用指令\examples"
uv run python verify.py
```

## 指令速查

| 指令 | 作用 | 是否产生层 |
| --- | --- | --- |
| `FROM` | 基础镜像 | 起始层 |
| `RUN` | 构建时执行命令 | **是** |
| `COPY` | 复制文件进镜像 | **是** |
| `ADD` | 同 COPY，支持 URL/解压 tar | **是** |
| `WORKDIR` | 后续指令的工作目录 | 否（元数据） |
| `ENV` | 环境变量 | 否 |
| `ARG` | 构建参数（仅构建期） | 否 |
| `EXPOSE` | 声明端口（仅文档） | 否 |
| `USER` | 运行用户 | 否 |
| `LABEL` | 镜像元数据 | 否 |
| `VOLUME` | 声明匿名卷挂载点 | 否 |
| `CMD` | 默认命令/参数 | 否 |
| `ENTRYPOINT` | 入口程序 | 否 |
| `HEALTHCHECK` | 健康检查 | 否 |

## CMD 与 ENTRYPOINT 的关系

| Dockerfile | `docker run img` | `docker run img --port 9000` |
| --- | --- | --- |
| `CMD ["python","app.py"]` | 执行 python app.py | **替换**为 `--port 9000`（报错） |
| `ENTRYPOINT ["python","app.py"]` + `CMD ["--port","8000"]` | `python app.py --port 8000` | `python app.py --port 9000` |

**结论：需要"固定入口 + 可变参数"时用 ENTRYPOINT + CMD 组合。**

## exec 形式 vs shell 形式

```dockerfile
CMD ["python", "app.py"]     # exec 形式：PID 1 是 python，能收到 SIGTERM
CMD python app.py            # shell 形式：PID 1 是 /bin/sh，信号可能传不到
```

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 容器收到 stop 不优雅退出 | shell 形式 CMD | 用 exec 形式 |
| `EXPOSE` 后以为外部能访问 | EXPOSE 只是声明 | 还要 `-p` 映射 |
| `ARG` 在运行时读不到 | ARG 仅构建期 | 需要运行时用 `ENV` |
| `ADD` 自动解压意外覆盖 | ADD 有副作用 | 优先用 COPY |
| 构建上下文过大 | 把 node_modules 也传了 | 加 `.dockerignore`（第 20 章） |
| 容器以 root 运行 | 默认 root | 加 `USER`（第 22 章） |
| `CMD` 里写 `&&` 失效 | exec 形式不经过 shell | 用 `sh -c "..."` |

## 毕业自查

- [ ] 13/13 通过
- [ ] 能说清 CMD 与 ENTRYPOINT 的区别
- [ ] 知道 exec 形式为什么更适合生产
- [ ] 知道 EXPOSE 不等于端口映射
