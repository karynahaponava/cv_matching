resource "yandex_iam_service_account" "tfstate_admin" {
  name      = "tfstate-admin-sa"
  folder_id = var.folder_id
}

resource "yandex_resourcemanager_folder_iam_member" "tfstate_admin_editor" {
  folder_id = var.folder_id
  role      = "storage.editor"
  member    = "serviceAccount:${yandex_iam_service_account.tfstate_admin.id}"
}

resource "yandex_iam_service_account_static_access_key" "tfstate_admin" {
  service_account_id = yandex_iam_service_account.tfstate_admin.id
}

module "s3_tfstate" {
  source = "../modules/S3"

  folder_id                          = var.folder_id
  bucket_name                        = var.tfstate_bucket_name
  service_account_name               = "tfstate-sa"
  versioning_enabled                 = true
  backup_retention_days              = 36500
  noncurrent_version_expiration_days = 90
  labels                             = var.labels

  admin_access_key = yandex_iam_service_account_static_access_key.tfstate_admin.access_key
  admin_secret_key = yandex_iam_service_account_static_access_key.tfstate_admin.secret_key
}
