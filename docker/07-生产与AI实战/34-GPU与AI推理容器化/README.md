# 34 GPU 与 AI 推理容器化

## 一句话结论

**模型权重永远不进镜像**：镜像只放代码与依赖，权重只读挂载、缓存用命名卷、批量数据走 stdin/stdout。GPU 只是"多声明一个设备"，但**声明成功不等于能用**——需要宿主驱动 + `nvidia-container-toolkit` + CUDA 基础镜像三者齐备。

## 最小可运行案例

```bash
docker run -d --name embed \
  --gpus all \
  -v /data/models:/models:ro \
  -v embedcache:/cache \
  -p 127.0.0.1:8000:8000 \
  --memory 8g --cpus 4 \
  my-embed:v1
```

## 怎么跑

```powershell
cd "07-生产与AI实战\34-GPU与AI推理容器化\examples"
uv run python verify.py
```

## 本机实测（24/24）

| 断言 | 实测 |
| --- | --- |
| 运行时列表 | `io.containerd.runc.v2`、`nvidia`、`runc` |
| CDI 目录 | `/etc/cdi`、`/var/run/cdi` |
| `--gpus all` | 容器正常启动 |
| `DeviceRequests` | `[{"Count":-1,"Capabilities":[["gpu"]]}]` |
| 容器内 `/dev/nvidia0` | **不存在** → 本机 WSL 未真正注入 GPU |
| `nvidia-smi`（alpine 镜像内） | `no such file or directory`（需 CUDA 镜像） |
| 模型只读挂载 | 容器内可读 48MB 权重，写失败 |
| 镜像内 `/models` | 空（模型没进镜像） |
| `/healthz` | 返回 `model_bytes=50331648` |
| `/embed` | 返回 8 维向量 |
| 批处理 `--batch` | 3 行输入 → 3 行输出 |
| 命名卷 `/cache` | 删容器后新容器仍能读到 `count=3` |
| `--memory 64m` + 申请 200MB | `OOMKilled=true`，退出码 137 |
| `HostConfig.Memory` | 67108864 |

## GPU 容器的三层依赖

```text
① 宿主驱动      nvidia-smi 在宿主能跑（Windows: NVIDIA 驱动 + WSL2 支持）
② 容器运行时    nvidia-container-toolkit（注册 nvidia runtime / 写 CDI 规范）
③ 镜像          CUDA/cuDNN 基础镜像（nvidia/cuda、pytorch/pytorch、vllm/vllm-openai）
```

缺任何一层，`--gpus all` 都不会真正给你算力。本章实测就撞上第 ①/③ 层：

| 现象 | 说明 |
| --- | --- |
| `nvidia` runtime 已注册 | 第 ② 层 OK |
| `/dev/nvidia0` 不存在 | 第 ① 层没通（WSL 未启用 GPU） |
| `nvidia-smi` 找不到 | 第 ③ 层缺失（用 alpine 而非 CUDA 镜像） |

排查顺序（从上往下）：

```bash
nvidia-smi                                  # 宿主
docker info --format '{{json .Runtimes}}'   # 运行时
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

## 模型与数据的三种放法

| 内容 | 放哪 | 理由 |
| --- | --- | --- |
| 代码、依赖 | 镜像 | 不可变、可版本化 |
| 模型权重 | **只读挂载**（宿主目录或对象存储同步目录） | 几 GB 到几百 GB，不进镜像 |
| 运行时缓存 | **命名卷** | 预热结果、tokenizer 缓存，跨容器复用 |
| 训练数据 | 挂载或对象存储 | 不能进镜像 |
| 输出/日志 | 卷 + stdout | 见第 31 章 |

反例：把 4GB 模型 `COPY` 进镜像 → 镜像仓库爆炸、每次构建拉全量层、多副本重复存储。

## 缓存与批处理

```bash
# 批处理：stdin 进、stdout 出，天然适合管道与临时容器
cat inputs.jsonl | docker run --rm -i -v $PWD/models:/models:ro my-embed:v1 python serve.py --batch > out.jsonl

# 一次性任务：不常驻、不占端口
docker run --rm -v /data/models:/models:ro my-embed:v1 python eval.py
```

批处理容器的优势：**没有端口、没有健康检查、随跑随删**，配合 `--rm` 与 `--cpus` 限流就是最简单的离线推理方案。

## 资源限制：显存与内存

| 资源 | 参数 | 说明 |
| --- | --- | --- |
| 内存 | `--memory` | **硬限制，超了 OOMKilled(137)** |
| CPU | `--cpus` | 近似核数 |
| GPU 数量 | `--gpus '"device=0,1"'` | 精确指定 |
| 显存 | 容器层面**无法直接限制** | 由应用控制（如 `gpu_memory_utilization`） |
| 共享内存 | `--shm-size=2g` | PyTorch DataLoader / 多进程必需 |

实测：`--memory 64m` 的容器申请 200MB 立刻被 OOMKill，`ExitCode=137`。

**显存是容器管不了的**：NVIDIA 没有 cgroup 级的显存限制，只能靠应用侧参数（vLLM 的 `--gpu-memory-utilization`、PyTorch 的 `torch.cuda.set_per_process_memory_fraction`）。多租户场景要用 MIG 或时间片调度。

`--shm-size` 是 AI 容器最容易漏的一项：默认 64MB，DataLoader 多 worker 时直接 `Bus error`。

## 生产 Compose 形态

```yaml
services:
  embed:
    build: .
    ports: ["127.0.0.1:18094:8000"]
    volumes:
      - ./models:/models:ro          # 权重只读
      - embedcache:/cache            # 缓存可写
    gpus: all                        # 需要 GPU 时才写
    shm_size: "2gb"
    environment:
      NVIDIA_VISIBLE_DEVICES: all
      NVIDIA_DRIVER_CAPABILITIES: compute,utility
    deploy:
      resources:
        limits: { cpus: "1.0", memory: 512M }
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')"]
      interval: 5s
volumes:
  embedcache:
```

`gpus: all` 是 Compose 的标准写法（等价 `docker run --gpus all`），`config` 校验**不需要真实 GPU**，所以在没有显卡的机器上也能验证配置。

## 常见 AI 服务镜像

| 场景 | 镜像 | 备注 |
| --- | --- | --- |
| 本地大模型 | `ollama/ollama` | `-v ollama:/root/.ollama` 挂模型 |
| 高吞吐推理 | `vllm/vllm-openai` | OpenAI 兼容 API，`--gpu-memory-utilization` |
| 文本嵌入 | `ghcr.io/huggingface/text-embeddings-inference` | TEI，小显存友好 |
| 向量库 | `pgvector/pgvector:pg16` | 第 13 章同款 + 向量扩展 |
| 训练 | `pytorch/pytorch`、`nvidia/cuda` | 需要 `--shm-size` 与 `--ipc=host` |
| 编排 | `langflow`、`n8n`、`dify` | 各有 compose 模板 |

## 最容易踩的坑

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `--gpus all` 但用不到 GPU | 宿主驱动/WSL GPU 未通 | 先 `nvidia-smi` 验证宿主 |
| `nvidia-smi: not found` | 用了非 CUDA 镜像 | 换 `nvidia/cuda` 等基础镜像 |
| `could not select device driver` | 未装 nvidia-container-toolkit | 安装并重启 docker |
| `Bus error` / DataLoader 崩 | `--shm-size` 太小 | `--shm-size=2g` |
| 容器被 OOMKilled(137) | 模型 + 批数据超 `--memory` | 加内存或减 batch |
| 显存 OOM 但容器内存正常 | 显存不受 cgroup 限制 | 调 `gpu_memory_utilization` |
| 镜像 4GB+ | 模型 COPY 进镜像 | 改挂载 |
| 多副本重复下载模型 | 每个容器各自拉 | 宿主共享目录 / 对象存储 + initContainer |
| 冷启动几十秒 | 每次重新加载权重 | 预热 + 缓存卷 + 常驻服务 |
| 多租户互相抢显存 | 无显存隔离 | MIG / 独立 GPU / 队列调度 |

## 毕业自查

- [ ] 24/24 通过
- [ ] 能说出 GPU 容器的三层依赖与排查顺序
- [ ] 能解释"声明了 --gpus 却用不到 GPU"的三种原因
- [ ] 能写出模型只读挂载 + 缓存卷的 compose 片段
- [ ] 能说出 `--shm-size` 为什么对 AI 容器重要
- [ ] 能解释为什么显存不能在容器层限制
- [ ] 能设计一个"模型外置 + 批处理 + 常驻服务"的双形态方案
