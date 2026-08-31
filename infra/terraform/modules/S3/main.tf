resource "yandex_iam_service_account" "this" {
    name = var.service_account_name
    folder_id = var.folder_id
}
resource "yandex_iam_service_account_static_access_key" "this" {
    service_account_id = yandex_iam_service_account.this.id
}
resource "yandex_storage_bucket" "this" {
    access_key = var.admin_access_key
    secret_key = var.admin_secret_key
    bucket = var.bucket_name
    acl = "private"
    folder_id = var.folder_id
    labels = var.labels
    versioning {
        enabled = var.versioning_enabled
    }
    lifecycle_rule {
        id = "retention"
        enabled = true
        expiration {
            days = var.backup_retention_days
        }
        noncurrent_version_expiration {
            days = var.noncurrent_version_expiration_days
        }
    }
    server_side_encryption_configuration {
    rule {
      apply_server_side_encryption_by_default {
        sse_algorithm = "AES256"
      }
    }
  }
}
resource "yandex_storage_bucket_iam_binding" "this" {
    bucket = yandex_storage_bucket.this.bucket
    role = "storage.editor"
    members = [
        "serviceAccount:${yandex_iam_service_account.this.id}"
    ]
}