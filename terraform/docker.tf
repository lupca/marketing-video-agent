# Build API Docker Image
locals {
  api_files = concat(
    tolist(fileset("${path.root}/..", "admin-api/**")),
    tolist(fileset("${path.root}/..", "shared_core/**")),
    tolist(fileset("${path.root}/..", ".dockerignore"))
  )
}
resource "docker_image" "api" {
  name = var.api_image

  build {
    context    = "${path.root}/.."
    dockerfile = "${path.root}/../admin-api/Dockerfile"
  }

  triggers = {
    dir_sha1 = sha1(join("", [
      for f in local.api_files :
      try(filesha1("${path.root}/../${f}"), "")
    ]))
  }
}

# Build Frontend Docker Image
resource "docker_image" "frontend" {
  name = var.frontend_image

  build {
    context    = "${path.root}/../frontend-admin"
    dockerfile = "${path.root}/../frontend-admin/Dockerfile"
  }

  triggers = {
    dir_sha1 = sha1(join("", [for f in fileset("${path.root}/../frontend-admin", "**") : filesha1("${path.root}/../frontend-admin/${f}")]))
  }
}
