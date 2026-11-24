# 26 Compose 入门与 YAML

## 一句话结论

Compose 把十几条 `docker run` 写进一个 `compose.yaml`，用 `docker compose up -d` 一次拉起整套服务。它只是**客户端的编排器**，最终仍然是逐个创建容器、网络、卷——所以前 25 章学的东西全都在用，只是不用手敲了。

## 最小可运行案例

```yaml
# compose.yaml
services:
  web:
    image: nginx:1.27-alpine
    ports:
      - "127.0.0.1:18080:80"
  worker:
    image: alpine:3.20
    command: ["sleep", "infinity"]
    depends_on:
      - web
```

```bash
docker compose up -d      # 启动
docker compose ps         # 看状态
docker compose logs -f    # 看日志
docker compose down       # 停掉并删除容器/网络
```

## 怎么跑

```powershell
cd "06-Compose编排\26-Compose入门与YAML\examples"
uv run python verify.py
```

## 本机实测（23/23）

| 步骤 | 实测结果 |
| --- | --- |
| `docker compose version --short` | `5.3.1` |
| `config -q` 校验合法文件 | 退出码 0 |
| `config --services` | `web`、`worker` |
| 命令行 `-p ch26-compose` | 覆盖文件里 `name: ch26-file`，最终项目名 `ch26-compose` |
| `GREETING: hello-${COMPOSE_TEST_USER:-guest}` + `.env` | 渲染成 `hello-bob` |
| `${NOT_SET_ANYWHERE:-guest}` | 渲染成 `guest` |
| 卷名 | 自动变成 `ch26-compose_data` |
| 非法文件（依赖不存在的 db） | `config` 非 0：`service "api" depends on undefined service "db"` |
| `up -d` | 两个容器 Started |
| 容器名 | `ch26-compose-web-1` |
| 标签 `com.docker.compose.project` / `.service` | `ch26-compose` / `web` |
| `ps --services` | `web`、`worker` |
| 访问 `127.0.0.1:18080` | `Welcome to nginx!` |
| `exec -T worker printenv MODE` | `demo` |
| `logs --no-color web` | 含请求路径 `/probe-from-verify-26` |
| 网络 `ch26-net` | 已创建，`len .Containers` = 2 |
| `down -v` | 容器、网络、卷全部删除 |

## YAML 顶层结构

| 键 | 作用 | 备注 |
| --- | --- | --- |
| `name` | 项目名 | 可被 `-p` / `COMPOSE_PROJECT_NAME` 覆盖 |
| `services` | 服务定义（**核心**） | 每个服务 = 一组容器 |
| `networks` | 自定义网络 | 不写则自动建 `{项目名}_default` |
| `volumes` | 命名卷 | 物理名 = `{项目名}_{卷名}` |
| `configs` / `secrets` | 配置文件 / 密钥 | 生产用，见第 29 章 |

**不要写 `version:`**。v2 起已废弃，本机实测会打印：

```text
level=warning msg="... the attribute `version` is obsolete, it will be ignored ..."
```

## 服务常用键

| 键 | 等价 docker run | 说明 |
| --- | --- | --- |
| `image` | 镜像名 | 与 `build` 二选一 |
| `build` | `docker build` | 可以是字符串或 `{context, dockerfile}` |
| `ports` | `-p` | 建议写 `"127.0.0.1:8080:80"` |
| `volumes` | `-v` | 短语法与长语法都支持 |
| `environment` | `-e` | 列表或字典，支持 `${VAR:-默认}` |
| `env_file` | `--env-file` | 多个文件后者覆盖前者 |
| `command` | 镜像后追加的命令 | 覆盖 Dockerfile 的 CMD |
| `entrypoint` | `--entrypoint` | 覆盖 ENTRYPOINT |
| `depends_on` | 无 | 只控制**启动顺序**，不等就绪（第 28 章） |
| `restart` | `--restart` | `no`/`always`/`unless-stopped`/`on-failure` |
| `healthcheck` | `HEALTHCHECK` | 覆盖镜像里的健康检查 |
| `networks` | `--network` | 可接多个网络 |
| `container_name` | `--name` | **不推荐**，会破坏 `--scale` |

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `docker compose config` | 渲染最终 YAML（含插值），**排查配置的第一选择** |
| `docker compose config -q` | 只校验，CI 门禁用 |
| `docker compose config --services` | 列出服务名 |
| `docker compose up -d` | 后台创建/更新 |
| `docker compose up -d --build` | 先重建镜像 |
| `docker compose ps` | 本项目容器状态 |
| `docker compose logs -f --tail 100 <svc>` | 跟日志 |
| `docker compose exec <svc> sh` | 进容器（`-T` 用于脚本） |
| `docker compose run --rm <svc> cmd` | 一次性任务容器 |
| `docker compose restart/stop/start <svc>` | 单个服务操作 |
| `docker compose down` | 删容器 + 网络 |
| `docker compose down -v` | 连命名卷一起删 |
| `docker compose ls` | 列出本机所有项目 |

## 项目名与容器名规则

```text
优先级：-p 参数  >  COMPOSE_PROJECT_NAME  >  顶层 name  >  所在目录名
容器名：{项目名}-{服务名}-{序号}      例：ch26-compose-web-1
默认网络：{项目名}_default
```

这也是本教程每章都用 `chNN-` 前缀的原因：**按项目名就能精确清理**，不会误删别人的容器。

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 目录名是中文/大写，项目名报错 | 项目名只允许小写字母、数字、`-`、`_` | 显式写 `name:` 或 `-p` |
| 改了 `.env` 不生效 | Compose 只在启动时读一次 | `up -d` 重新创建 |
| `up` 后容器立刻退出 | 主进程不是前台常驻（如 `sh -c "echo hi"`） | 用 `sleep infinity` / 真正的服务进程 |
| `ports` 冲突 | 宿主机端口被占 | 换端口或绑 `127.0.0.1:` |
| 数据"丢了" | 卷名带了项目名前缀，换了项目名就成了新卷 | 用 `external: true` 或固定 `name:` |
| 改了镜像 tag 但容器没变 | `up` 只在配置变化时重建 | `up -d --force-recreate` |
| 想改容器名 | `container_name` 写死 | 别写，用服务名寻址 |
| YAML 缩进用 Tab | YAML 只认空格 | 2 空格 |

## 毕业自查

- [ ] 23/23 通过
- [ ] 能背出 `services`/`networks`/`volumes` 三个顶层键的作用
- [ ] 能说出项目名的 4 级优先级
- [ ] 知道 `config` 为什么是排查第一选择
- [ ] 知道 `down` 和 `down -v` 的区别
