# docker buildx bake：用声明式文件描述"一次构建多个镜像"
variable "TAG" {
  default = "dev"
}

group "default" {
  targets = ["api", "worker"]
}

# 公共配置：多个 target 继承，避免重复
target "common" {
  context    = "."
  dockerfile = "Dockerfile"
  args = {
    APP_VERSION = TAG
  }
  platforms = ["linux/amd64"]
}

target "api" {
  inherits = ["common"]
  target   = "api"
  tags     = ["ch33-api:${TAG}"]
  # 每个 target 用独立的缓存目录：多个 target 并发写同一目录会冲突
  cache-from = ["type=local,src=./.buildcache/api"]
  cache-to   = ["type=local,dest=./.buildcache/api,mode=max"]
}

target "worker" {
  inherits = ["common"]
  target   = "worker"
  tags     = ["ch33-worker:${TAG}"]
}
