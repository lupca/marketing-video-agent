variable "namespace" {
  description = "Kubernetes namespace"
  type        = string
  default     = "video-creator"
}

variable "kubernetes_config_path" {
  description = "Path to Kubernetes config file"
  type        = string
  default     = "~/.kube/config"
}

variable "kubernetes_context" {
  description = "Kubernetes context to use"
  type        = string
  default     = "docker-desktop"
}

variable "docker_host" {
  description = "Docker daemon host"
  type        = string
  default     = "unix:///var/run/docker.sock"
}

variable "api_image" {
  description = "API Docker image"
  type        = string
  default     = "marketing-video-agent:latest"
}

variable "frontend_image" {
  description = "Frontend Docker image"
  type        = string
  default     = "marketing-video-agent-frontend:latest"
}

variable "api_replicas" {
  description = "Number of API replicas"
  type        = number
  default     = 1
}

variable "worker_review_replicas" {
  description = "Number of worker-review replicas"
  type        = number
  default     = 1
}

variable "worker_research_replicas" {
  description = "Number of worker-research replicas"
  type        = number
  default     = 1
}

variable "worker_slideshow_replicas" {
  description = "Number of worker-slideshow replicas"
  type        = number
  default     = 1
}

variable "worker_promotion_replicas" {
  description = "Number of worker-promotion replicas"
  type        = number
  default     = 1
}

variable "worker_download_replicas" {
  description = "Number of worker-download replicas"
  type        = number
  default     = 1
}

# Database variables
variable "database_user" {
  description = "Database username"
  type        = string
  sensitive   = true
  default     = "video_creator"
}

variable "database_password" {
  description = "Database password"
  type        = string
  sensitive   = true
  default     = "video_password_123"
}

variable "postgres_password" {
  description = "PostgreSQL admin password"
  type        = string
  sensitive   = true
  default     = "postgres_123"
}

# MinIO variables
variable "minio_root_user" {
  description = "MinIO root user"
  type        = string
  sensitive   = true
  default     = "minioadmin"
}

variable "minio_root_password" {
  description = "MinIO root password"
  type        = string
  sensitive   = true
  default     = "minioadmin"
}

# App secrets
variable "secret_key" {
  description = "Application secret key"
  type        = string
  sensitive   = true
  default     = "your-secret-key-change-this-in-production"
}

variable "algorithm" {
  description = "JWT algorithm"
  type        = string
  default     = "HS256"
}

# Storage sizes
variable "postgres_storage" {
  description = "PostgreSQL storage size"
  type        = string
  default     = "10Gi"
}

variable "minio_storage" {
  description = "MinIO storage size"
  type        = string
  default     = "20Gi"
}

variable "redis_storage" {
  description = "Redis storage size"
  type        = string
  default     = "2Gi"
}

# Resource limits
variable "api_cpu_request" {
  description = "API CPU request"
  type        = string
  default     = "100m"
}

variable "api_cpu_limit" {
  description = "API CPU limit"
  type        = string
  default     = "500m"
}

variable "api_memory_request" {
  description = "API memory request"
  type        = string
  default     = "256Mi"
}

variable "api_memory_limit" {
  description = "API memory limit"
  type        = string
  default     = "1Gi"
}

variable "worker_cpu_request" {
  description = "Worker CPU request"
  type        = string
  default     = "200m"
}

variable "worker_cpu_limit" {
  description = "Worker CPU limit"
  type        = string
  default     = "1000m"
}

variable "worker_memory_request" {
  description = "Worker memory request"
  type        = string
  default     = "512Mi"
}

variable "worker_memory_limit" {
  description = "Worker memory limit"
  type        = string
  default     = "2Gi"
}
