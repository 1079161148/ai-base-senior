# Ollama 本地大模型部署

## 一、本地模型方案对比

| 方案 | 定位 | 特点 |
|------|------|------|
| **PyTorch + Transformers** | 本地训练 / 微调 / 推理 | 灵活度最高，但需自行适配硬件加速 |
| **Ollama** | 一键部署运行开源大模型 | 命令行工具，内置量化支持与 GPU 加速 |
| **llama.cpp** | 高性能推理引擎 | C/C++ 实现，主打 **CPU 推理**与多种量化方案 |
| **vLLM** | 高吞吐推理框架 | 基于 **PagedAttention**，适合生产环境部署 |
| **MLX** | Apple 官方 ML 框架 | 专为 **Apple Silicon** 设计的本地推理方案 |
| **LM Studio** | 桌面图形应用 | 一键下载并运行本地开源模型，适合新手 |
| **LocalAI** | 本地推理服务 | 提供 **OpenAI 兼容 API**，现有应用可无缝切换 |

> 选型思路：想省事用 Ollama / LM Studio；要生产高并发用 vLLM；Mac 上用 MLX；资源受限或纯 CPU 场景用 llama.cpp。

## 二、下载安装

官方下载地址：https://ollama.com/

安装完成后验证：

```shell
ollama -v
```

Ollama 官方模型仓库：https://ollama.com/library

### 镜像加速（可选）

```shell
# 设置模型下载镜像，加速拉取（视镜像服务商而定，非官方标准变量）
OLLAMA_MODEL_SERVER="https://mirror.ollama.com"
```

## 三、常用命令

| 命令 | 说明 |
|------|------|
| `ollama pull <模型名>` | 拉取模型到本地 |
| `ollama list` | 查看已下载的模型 |
| `ollama rm <模型名>` | 删除模型 |
| `ollama show <模型名>` | 查看模型信息 |
| `ollama run <模型名>` | 运行模型（进入交互式对话） |
| `ollama ps` | 查看当前正在运行的服务 |

示例：

```shell
# 拉取模型
ollama pull qwen3-vl

# 查看本地模型
ollama list

# 运行模型
ollama run qwen3-vl
```

服务启动后，访问 http://localhost:11434/ 可确认服务是否在运行。

> 提示：Ollama 默认监听 `11434` 端口；如需修改，可通过 `OLLAMA_HOST` 环境变量调整。

## 四、接口测试

Ollama 提供 OpenAI 兼容接口，前缀为 `/v1`。

### 模型列表

```shell
curl http://localhost:11434/v1/models
```

### 聊天接口

```shell
curl -X POST http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"qwen3-vl\", \"messages\": [{\"role\": \"user\", \"content\": \"你好，你是什么模型？\"}], \"stream\": false}"
```

### 补充：原生 API

除 OpenAI 兼容接口外，Ollama 还提供原生接口：

| 接口 | 说明 |
|------|------|
| `GET /api/tags` | 列出本地模型 |
| `POST /api/generate` | 单轮文本生成 |
| `POST /api/chat` | 多轮对话 |
| `POST /api/embed` | 文本向量化（Embedding） |

## 五、注意事项

- 首次 `pull` 需下载模型权重，体积较大，建议配置镜像或代理。
- 默认量化版本为 `q4` 系列，平衡体积与精度；需要更高精度可显式指定量化标签。
- 本地模型性能高度依赖硬件：显存不足会自动降级到 CPU 推理，速度明显变慢。
- 若用于生产，注意 Ollama 更适合单机轻量场景，高并发请评估 vLLM。
