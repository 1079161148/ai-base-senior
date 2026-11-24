# 23 仓库概念与推送流程

## 一句话结论

仓库（Registry）是存镜像的服务。push 前必须把镜像 tag 改成 `仓库地址/命名空间/镜像名:标签` 的完整形式，然后 `docker login` + `docker push`。**tag 只是本地别名，push 的是它的完整名字。**

## 最小可运行案例

```bash
docker tag myapp:1.0 registry.cn-hangzhou.aliyuncs.com/myns/myapp:1.0
docker login registry.cn-hangzhou.aliyuncs.com
docker push registry.cn-hangzhou.aliyuncs.com/myns/myapp:1.0
docker pull registry.cn-hangzhou.aliyuncs.com/myns/myapp:1.0
```

## 怎么跑

```powershell
cd "05-镜像仓库\23-仓库概念与推送流程\examples"
uv run python verify.py
```

## 常见仓库

| 仓库 | 地址 | 说明 |
| --- | --- | --- |
| Docker Hub | `docker.io` | 默认，公共免费额度有限 |
| 阿里云 ACR | `registry.cn-hangzhou.aliyuncs.com` | 国内快，个人版免费 |
| 腾讯云 TCR | `ccr.ccs.tencentyun.com` | 企业版功能全 |
| 华为云 SWR | `swr.cn-north-4.myhuaweicloud.com` | |
| GitHub GHCR | `ghcr.io` | 与 Actions 集成 |
| 自建 | `harbor.example.com` | 第 25 章 |

## 推送命令模板

```bash
# 1. 登录（密码可用 --password-stdin 避免进历史）
echo "$TOKEN" | docker login $REGISTRY -u $USER --password-stdin

# 2. 打完整标签
docker tag $LOCAL_IMAGE $REGISTRY/$NAMESPACE/$IMAGE:$TAG

# 3. 推送
docker push $REGISTRY/$NAMESPACE/$IMAGE:$TAG

# 4. 退出
docker logout $REGISTRY
```

## 本机实测

| 检查 | 结果 |
| --- | --- |
| 本地标签 | 成功 |
| 带仓库前缀的标签 | 成功 |
| push 到 `localhost:5999` | 失败（连接被拒，尝试 HTTPS） |
| 凭证位置 | `C:\Users\<用户>\.docker\config.json` |
| 默认仓库 | `https://index.docker.io/v1/` |
| 镜像 digest | `alpine@sha256:d9e853...` |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| push 报 `denied` | 未登录或无权限 | `docker login` / 检查命名空间 |
| push 报 `https` 错误 | 自建仓库用 HTTP | 配 `insecure-registries`（第 05 章） |
| 推上去的 tag 不对 | 只 tag 了短名 | 用完整名 tag |
| 密码进了 shell 历史 | 用了 `-p` 明文 | `--password-stdin` |
| 拉取慢 | 未配加速 | 第 05 章 |
| 生产用 latest | 版本漂移 | 固定 tag + digest |
| 多架构推不上去 | 单平台构建 | `buildx --platform` |
| 免费额度用完 | Hub 限流 | 用云厂商仓库 |

## 毕业自查

- [ ] 11/11 通过
- [ ] 能完整说出 push 的四步
- [ ] 知道 `config.json` 存了什么
- [ ] 知道为什么要用 `--password-stdin`
