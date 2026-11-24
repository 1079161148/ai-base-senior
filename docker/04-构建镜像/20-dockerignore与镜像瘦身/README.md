# 20 .dockerignore 与镜像瘦身

## 一句话结论

镜像瘦身两个动作：**`.dockerignore` 不把无关文件送进构建上下文**，**同一 RUN 里"用完就删"**。记住一条铁律：**跨层删除不会减小镜像**——层不可变，删掉的只是"删除标记"，数据还在下面的层里。

## 最小可运行案例

```text
# .dockerignore
node_modules
.git
*.log
dist
.env
```

```dockerfile
# 正确：创建与删除放在同一个 RUN
RUN dd if=/dev/urandom of=/tmp/big bs=1M count=10 && rm -f /tmp/big
```

## 怎么跑

```powershell
cd "04-构建镜像\20-dockerignore与镜像瘦身\examples"
uv run python verify.py
```

## 本机实测对比

| 场景 | 镜像体积 |
| --- | --- |
| 无 `.dockerignore`（含 5MB 文件） | 8 MB |
| 有 `.dockerignore` 排除该文件 | 3 MB |
| 同一 RUN 创建 10MB 再删除 | 3 MB |
| 跨两个 RUN 创建再删除 | **13 MB**（10MB 幽灵数据） |

最后一行是最重要的教学点：分两层做，镜像反而大了 10MB。

## .dockerignore 语法

| 写法 | 含义 |
| --- | --- |
| `node_modules` | 排除该目录 |
| `*.log` | 通配符 |
| `!important.log` | 例外（不排除） |
| `**/*.md` | 递归匹配 |
| `.git` | 排除版本库 |

## 瘦身清单

| 手段 | 效果 |
| --- | --- |
| 用 `alpine`/`slim` 基础镜像 | 从 GB 降到几十 MB |
| `.dockerignore` | 不传无关文件 |
| 同层创建+删除 | 避免幽灵数据 |
| 清理包管理缓存 | `rm -rf /var/lib/apt/lists/*`、`apk --no-cache` |
| 多阶段构建 | 最终镜像只留运行产物（第 21 章） |
| 合并 RUN | 减少层数 |
| 用 `.tar` 而非 git 目录 | 避免 `.git` 膨胀 |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| 删了文件镜像还变大 | 跨层删除 | 同一 RUN 内删除 |
| 构建很慢 | 上下文几百 MB | `.dockerignore` |
| 密钥被构建进镜像 | 忘了 ignore `.env` | 加 ignore 并用 secrets |
| `COPY . .` 带进 node_modules | 无 ignore | 加 ignore |
| apk 缓存残留 | 没用 `--no-cache` | `apk add --no-cache` |
| `.git` 进了镜像 | 无 ignore | 排除 `.git` |
| 层数过多 | RUN 太碎 | 合理合并 |

## 毕业自查

- [ ] 7/7 通过
- [ ] 能解释为什么跨层删除不减小镜像
- [ ] 会写基础 `.dockerignore`
- [ ] 知道 `--no-cache` 与图层缓存的区别
