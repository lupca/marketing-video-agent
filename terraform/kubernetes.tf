# PostgreSQL StatefulSet
resource "kubernetes_stateful_set" "postgresql" {
  metadata {
    name      = "db"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    service_name = "db"
    replicas     = 1

    selector {
      match_labels = {
        app = "postgresql"
      }
    }

    template {
      metadata {
        labels = {
          app = "postgresql"
        }
      }

      spec {
        container {
          name  = "postgresql"
          image = "postgres:15-alpine"

          port {
            container_port = 5432
          }

          env {
            name  = "POSTGRES_DB"
            value = "video_creator"
          }

          env {
            name  = "POSTGRES_HOST_AUTH_METHOD"
            value = "trust"
          }

          env {
            name = "POSTGRES_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.app_secrets.metadata[0].name
                key  = "DATABASE_USER"
              }
            }
          }

          env {
            name = "POSTGRES_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.app_secrets.metadata[0].name
                key  = "POSTGRES_PASSWORD"
              }
            }
          }

          volume_mount {
            name       = "postgres-storage"
            mount_path = "/var/lib/postgresql/data"
          }
          volume_mount {
            name       = "init-script"
            mount_path = "/docker-entrypoint-initdb.d"
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "1Gi"
            }
          }
        }

        volume {
          name = "postgres-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.postgres_pvc.metadata[0].name
          }
        }
        volume {
          name = "init-script"
          config_map {
            name = kubernetes_config_map.postgres_init.metadata[0].name
          }
        }
      }
    }
  }
}

# PostgreSQL Service
resource "kubernetes_service" "postgresql" {
  metadata {
    name      = "db"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    selector = {
      app = "postgresql"
    }

    port {
      port        = 5432
      target_port = 5432
    }
  }
}

# Redis Deployment
resource "kubernetes_deployment" "redis" {
  metadata {
    name      = "redis"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "redis"
      }
    }

    template {
      metadata {
        labels = {
          app = "redis"
        }
      }

      spec {
        container {
          name  = "redis"
          image = "redis:7-alpine"

          port {
            container_port = 6379
          }

          volume_mount {
            name       = "redis-storage"
            mount_path = "/data"
          }

          resources {
            requests = {
              cpu    = "50m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "200m"
              memory = "512Mi"
            }
          }
        }

        volume {
          name = "redis-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.redis_pvc.metadata[0].name
          }
        }
      }
    }
  }
}

# Redis Service
resource "kubernetes_service" "redis" {
  metadata {
    name      = "redis"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    selector = {
      app = "redis"
    }

    port {
      port        = 6379
      target_port = 6379
    }
  }
}

# MinIO StatefulSet
resource "kubernetes_stateful_set" "minio" {
  metadata {
    name      = "minio"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    service_name = "minio"
    replicas     = 1

    selector {
      match_labels = {
        app = "minio"
      }
    }

    template {
      metadata {
        labels = {
          app = "minio"
        }
      }

      spec {
        container {
          name  = "minio"
          image = "minio/minio:latest"

          args = ["server", "/bitnami/minio/data"]

          port {
            name           = "minio"
            container_port = 9000
          }

          port {
            name           = "console"
            container_port = 9001
          }

          env {
            name = "MINIO_ROOT_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.app_secrets.metadata[0].name
                key  = "MINIO_ROOT_USER"
              }
            }
          }

          env {
            name = "MINIO_ROOT_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.app_secrets.metadata[0].name
                key  = "MINIO_ROOT_PASSWORD"
              }
            }
          }

          volume_mount {
            name       = "minio-storage"
            mount_path = "/bitnami/minio/data"
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "256Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "1Gi"
            }
          }
        }

        volume {
          name = "minio-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.minio_pvc.metadata[0].name
          }
        }
      }
    }
  }
}

# MinIO Service
resource "kubernetes_service" "minio" {
  metadata {
    name      = "minio"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    selector = {
      app = "minio"
    }

    port {
      name        = "minio"
      port        = 9000
      target_port = 9000
    }

    port {
      name        = "console"
      port        = 9001
      target_port = 9001
    }
  }
}

# API Deployment
resource "kubernetes_deployment" "api" {
  metadata {
    name      = "api"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  depends_on = [
    kubernetes_deployment.redis,
    kubernetes_stateful_set.postgresql,
    kubernetes_stateful_set.minio,
  ]

  spec {
    replicas = var.api_replicas

    selector {
      match_labels = {
        app = "api"
      }
    }

    template {
      metadata {
        labels = {
          app = "api"
        }
      }

      spec {
        container {
          name  = "api"
          image = var.api_image

          image_pull_policy = "Never"

          port {
            container_port = 8000
          }

          env_from {
            config_map_ref {
              name = kubernetes_config_map.app_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.app_secrets.metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = var.api_cpu_request
              memory = var.api_memory_request
            }
            limits = {
              cpu    = var.api_cpu_limit
              memory = var.api_memory_limit
            }
          }

          liveness_probe {
            http_get {
              path = "/docs"
              port = 8000
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/docs"
              port = 8000
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }
      }
    }
  }
}

# API Service
resource "kubernetes_service" "api" {
  metadata {
    name      = "api"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    selector = {
      app = "api"
    }

    port {
      port        = 8000
      target_port = 8000
    }

    type = "LoadBalancer"
  }
}

# Frontend Deployment
resource "kubernetes_deployment" "frontend" {
  metadata {
    name      = "frontend"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "frontend"
      }
    }

    template {
      metadata {
        labels = {
          app = "frontend"
        }
      }

      spec {
        container {
          name  = "frontend"
          image = var.frontend_image

          image_pull_policy = "Never"

          port {
            container_port = 80
          }

          resources {
            requests = {
              cpu    = "100m"
              memory = "128Mi"
            }
            limits = {
              cpu    = "500m"
              memory = "512Mi"
            }
          }

          readiness_probe {
            http_get {
              path = "/"
              port = 80
            }
            initial_delay_seconds = 5
            period_seconds        = 5
          }
        }
      }
    }
  }
}

# Frontend Service
resource "kubernetes_service" "frontend" {
  metadata {
    name      = "frontend"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    selector = {
      app = "frontend"
    }

    port {
      port        = 80
      target_port = 80
    }

    type = "LoadBalancer"
  }
}

# Worker Deployments (Review, Research, Slideshow, Promotion, Download)
resource "kubernetes_deployment" "worker_review" {
  metadata {
    name      = "worker-review"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  depends_on = [
    kubernetes_deployment.redis,
    kubernetes_stateful_set.postgresql,
  ]

  spec {
    replicas = var.worker_review_replicas

    selector {
      match_labels = {
        app = "worker-review"
      }
    }

    template {
      metadata {
        labels = {
          app = "worker-review"
        }
      }

      spec {
        container {
          name  = "worker-review"
          image = var.api_image

          image_pull_policy = "Never"

          env_from {
            config_map_ref {
              name = kubernetes_config_map.app_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.app_secrets.metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = var.worker_cpu_request
              memory = var.worker_memory_request
            }
            limits = {
              cpu    = var.worker_cpu_limit
              memory = var.worker_memory_limit
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_deployment" "worker_research" {
  metadata {
    name      = "worker-research"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  depends_on = [
    kubernetes_deployment.redis,
    kubernetes_stateful_set.postgresql,
  ]

  spec {
    replicas = var.worker_research_replicas

    selector {
      match_labels = {
        app = "worker-research"
      }
    }

    template {
      metadata {
        labels = {
          app = "worker-research"
        }
      }

      spec {
        container {
          name  = "worker-research"
          image = var.api_image

          image_pull_policy = "Never"

          env_from {
            config_map_ref {
              name = kubernetes_config_map.app_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.app_secrets.metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = var.worker_cpu_request
              memory = var.worker_memory_request
            }
            limits = {
              cpu    = var.worker_cpu_limit
              memory = var.worker_memory_limit
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_deployment" "worker_slideshow" {
  metadata {
    name      = "worker-slideshow"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  depends_on = [
    kubernetes_deployment.redis,
    kubernetes_stateful_set.postgresql,
  ]

  spec {
    replicas = var.worker_slideshow_replicas

    selector {
      match_labels = {
        app = "worker-slideshow"
      }
    }

    template {
      metadata {
        labels = {
          app = "worker-slideshow"
        }
      }

      spec {
        container {
          name  = "worker-slideshow"
          image = var.api_image

          image_pull_policy = "Never"

          env_from {
            config_map_ref {
              name = kubernetes_config_map.app_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.app_secrets.metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = var.worker_cpu_request
              memory = var.worker_memory_request
            }
            limits = {
              cpu    = var.worker_cpu_limit
              memory = var.worker_memory_limit
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_deployment" "worker_promotion" {
  metadata {
    name      = "worker-promotion"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  depends_on = [
    kubernetes_deployment.redis,
    kubernetes_stateful_set.postgresql,
  ]

  spec {
    replicas = var.worker_promotion_replicas

    selector {
      match_labels = {
        app = "worker-promotion"
      }
    }

    template {
      metadata {
        labels = {
          app = "worker-promotion"
        }
      }

      spec {
        container {
          name  = "worker-promotion"
          image = var.api_image

          image_pull_policy = "Never"

          env_from {
            config_map_ref {
              name = kubernetes_config_map.app_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.app_secrets.metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = var.worker_cpu_request
              memory = var.worker_memory_request
            }
            limits = {
              cpu    = var.worker_cpu_limit
              memory = var.worker_memory_limit
            }
          }
        }
      }
    }
  }
}

resource "kubernetes_deployment" "worker_download" {
  metadata {
    name      = "worker-download"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  depends_on = [
    kubernetes_deployment.redis,
    kubernetes_stateful_set.postgresql,
  ]

  spec {
    replicas = var.worker_download_replicas

    selector {
      match_labels = {
        app = "worker-download"
      }
    }

    template {
      metadata {
        labels = {
          app = "worker-download"
        }
      }

      spec {
        container {
          name  = "worker-download"
          image = var.api_image

          image_pull_policy = "Never"

          env_from {
            config_map_ref {
              name = kubernetes_config_map.app_config.metadata[0].name
            }
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.app_secrets.metadata[0].name
            }
          }

          resources {
            requests = {
              cpu    = var.worker_cpu_request
              memory = var.worker_memory_request
            }
            limits = {
              cpu    = var.worker_cpu_limit
              memory = var.worker_memory_limit
            }
          }
        }
      }
    }
  }
}
