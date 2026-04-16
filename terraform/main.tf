terraform {
  required_version = ">= 1.0"
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }

  # Optional: Store state remotely
  # backend "local" {
  #   path = "terraform.tfstate"
  # }
}

# Kubernetes Provider
provider "kubernetes" {
  config_path    = var.kubernetes_config_path
  config_context = var.kubernetes_context
}

# Docker Provider
provider "docker" {
  host = var.docker_host
}

# Create namespace
resource "kubernetes_namespace" "video_creator" {
  metadata {
    name = var.namespace
  }

  lifecycle {
    ignore_changes = [metadata[0].uid, metadata[0].resource_version]
  }
}

# Create ConfigMap for environment variables
resource "kubernetes_config_map" "app_config" {
  metadata {
    name      = "app-config"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  data = {
    DATABASE_URL = "postgresql://admin:password123@db:5432/video_creator"
  REDIS_URL    = "redis://redis:6379/0"

  MINIO_ENDPOINT = "minio:9000"
  MINIO_BUCKET   = "videos"

  CELERY_BROKER  = "redis://redis:6379/0"
  CELERY_BACKEND = "redis://redis:6379/1"
    DATABASE_HOST    = "db"
    DATABASE_PORT    = "5432"
    DATABASE_DB      = "video_creator"
    REDIS_HOST       = "redis"
    REDIS_PORT       = "6379"
    MINIO_ENDPOINT   = "minio:9000"
    MINIO_BUCKET     = "videos"
    CELERY_BROKER    = "redis://redis:6379/0"
    CELERY_BACKEND   = "redis://redis:6379/1"
  }
}

# Create Secret for sensitive data
resource "kubernetes_secret" "app_secrets" {
  metadata {
    name      = "app-secrets"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  data = {
    DATABASE_USER      = base64encode(var.database_user)
    DATABASE_PASSWORD  = base64encode(var.database_password)
    POSTGRES_PASSWORD  = base64encode(var.postgres_password)
    MINIO_ROOT_USER    = base64encode(var.minio_root_user)
    MINIO_ROOT_PASSWORD = base64encode(var.minio_root_password)
    SECRET_KEY         = base64encode(var.secret_key)
    ALGORITHM          = base64encode(var.algorithm)
  }

  type = "Opaque"
}

resource "kubernetes_config_map" "postgres_init" {
  metadata {
    name      = "postgres-init"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  data = {
    "init.sql" = <<-EOT
      CREATE USER admin WITH PASSWORD 'password123';
      ALTER USER admin WITH SUPERUSER;
      CREATE DATABASE video_creator OWNER admin;
    EOT
  }
}



# Create PersistentVolumeClaims
resource "kubernetes_persistent_volume_claim" "postgres_pvc" {
  metadata {
    name      = "postgres-pvc"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = var.postgres_storage
      }
    }
  }
}

resource "kubernetes_persistent_volume_claim" "minio_pvc" {
  metadata {
    name      = "minio-pvc"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = var.minio_storage
      }
    }
  }
}

resource "kubernetes_persistent_volume_claim" "redis_pvc" {
  metadata {
    name      = "redis-pvc"
    namespace = kubernetes_namespace.video_creator.metadata[0].name
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = var.redis_storage
      }
    }
  }
}
