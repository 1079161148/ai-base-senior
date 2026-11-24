# 23 仓库概念与推送流程 · 完整版

## 0. 怎么用

跑 11/11。本章不需要真实账号，验证命名规范、认证要求、凭证位置与 digest。

## 1. 概念

| 术语 | 含义 |
| --- | --- |
| Registry | 仓库服务（docker.io、ACR、Harbor） |
| Repository | 仓库内的镜像名（如 `library/nginx`） |
| Namespace | 命名空间/用户/组织 |
| Tag | 版本标签，可覆盖 |
| Digest | 内容哈希，不可变 |

## 2. 机制

```text
docker push REG/NS/IMG:TAG
  → 读取 ~/.docker/config.json 取认证
  → 逐层上传（已存在的层跳过）
  → 上传 manifest（含 config + layers digest）
docker pull 反之，按层去重下载
```

## 3. 各平台推送实操

### 阿里云 ACR

```bash
docker login --username=你的账号 registry.cn-hangzhou.aliyuncs.com
docker tag myapp:1.0 registry.cn-hangzhou.aliyuncs.com/命名空间/myapp:1.0
docker push registry.cn-hangzhou.aliyuncs.com/命名空间/myapp:1.0
```

### 腾讯云 TCR

```bash
docker login ccr.ccs.tencentyun.com --username=1000xxxx
docker tag myapp:1.0 ccr.ccs.tencentyun.com/命名空间/myapp:1.0
docker push ccr.ccs.tencentyun.com/命名空间/myapp:1.0
```

### GitHub GHCR

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u 用户名 --password-stdin
docker tag myapp:1.0 ghcr.io/用户名/myapp:1.0
docker push ghcr.io/用户名/myapp:1.0
```

### Docker Hub

```bash
docker login
docker tag myapp:1.0 用户名/myapp:1.0
docker push 用户名/myapp:1.0
```

## 4. 边界条件

- 自建 HTTP 仓库必须配 `insecure-registries`，否则按 HTTPS 访问失败（本机实测 `localhost:5999` 走 HTTPS 直接连不上）。
- tag 可被覆盖，digest 不可变；生产用 digest 部署防漂移。
- Docker Hub 未登录也能 pull 公共镜像，但 push 必须登录。
- 多架构镜像需要 `buildx build --platform linux/amd64,linux/arm64 --push`。
- 凭证默认 base64 存在 `config.json`，共享机器要 `docker logout`。

## 5. 注意事项对照表

| 错误做法 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 不 login 就 push | `denied` | 先登录 | 实测 |
| 用短名 push | 推到 docker.io 意外位置 | 完整名 tag | 实测 |
| 明文 `-p 密码` | 进 shell 历史 | `--password-stdin` | 安全 |
| 自建 HTTP 仓库不配 | HTTPS 报错 | insecure-registries | 实测 |
| 只推 latest | 无法回溯 | 语义化 tag | 第 06 章 |
| 不 logout 共享机 | 凭证泄露 | 用完 logout | 安全 |
| 手工推多架构 | 只有单平台 | buildx --platform | 官方 |
| 忽略 digest | 版本漂移 | tag+digest 双保险 | 最佳实践 |
| 仓库无权限规划 | 谁都能推 | RBAC/项目隔离 | 第 25 章 |
| 跳过验收 | 流程不熟 | 11/11 再走 | 实测 |

## 6. 最佳实践

CI 里用机器账号 + token + `--password-stdin`；tag 采用 `版本-commit`；生产拉取用 digest；仓库开启漏洞扫描与镜像签名。

## 7. 依据索引

| 编号 | 类型 | 内容 |
| --- | --- | --- |
| `[r1]` | Docker 官方文档 | 本章涉及的 CLI、配置与生产实践 |
| `[r2]` | 官方 | docker push / login |
| `[r3]` | 实测 | 11/11，含不可达仓库报错 |

## 8. 毕业自查

- [ ] 11/11 通过
- [ ] 能默写 push 四步

## 9. 下一章

第 24 章自建本地 Registry，做一次真实的 push/pull 闭环。
