output "namespace" {
  description = "Kubernetes namespace"
  value       = kubernetes_namespace.video_creator.metadata[0].name
}

output "api_service" {
  description = "API service endpoint"
  value       = kubernetes_service.api.metadata[0].name
}

output "frontend_service" {
  description = "Frontend service endpoint"
  value       = kubernetes_service.frontend.metadata[0].name
}

output "postgresql_service" {
  description = "PostgreSQL service endpoint"
  value       = kubernetes_service.postgresql.metadata[0].name
}

output "redis_service" {
  description = "Redis service endpoint"
  value       = kubernetes_service.redis.metadata[0].name
}

output "minio_service" {
  description = "MinIO service endpoint"
  value       = kubernetes_service.minio.metadata[0].name
}

output "api_image_id" {
  description = "API Docker image ID"
  value       = docker_image.api.image_id
}

output "frontend_image_id" {
  description = "Frontend Docker image ID"
  value       = docker_image.frontend.image_id
}

output "port_forward_commands" {
  description = "Commands to port-forward services"
  value = {
    api      = "kubectl port-forward -n ${kubernetes_namespace.video_creator.metadata[0].name} svc/api 9100:9100"
    frontend = "kubectl port-forward -n ${kubernetes_namespace.video_creator.metadata[0].name} svc/frontend 3000:80"
    minio    = "kubectl port-forward -n ${kubernetes_namespace.video_creator.metadata[0].name} svc/minio 9000:9000"
  }
}

output "access_urls" {
  description = "Application access URLs"
  value = {
    api      = "http://localhost:9100/docs"
    frontend = "http://localhost:3000"
    minio    = "http://localhost:9000"
  }
}
