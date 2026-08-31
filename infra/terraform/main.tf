resource "yandex_iam_service_account" "storage_admin" {
  name = "storage-admin-sa"
  folder_id = var.folder_id
}
resource "yandex_resourcemanager_folder_iam_member" "storage_admin_editor" {
  folder_id = var.folder_id
  role = "storage.editor"
  member = "serviceAccount:${yandex_iam_service_account.storage_admin.id}"
}
resource "yandex_iam_service_account_static_access_key" "storage_admin" {
  service_account_id = yandex_iam_service_account.storage_admin.id
}
module "vm" {
  source = "./modules/VM"
  folder_id = var.folder_id
  zone = var.zone
  instance_name = var.instance_name
  subnet_id = var.subnet_id
  security_group_ids = var.security_group_ids
  cores = var.cores
  memory = var.memory
  core_fraction = var.core_fraction
  boot_disk_size = var.boot_disk_size
  ssh_user = var.ssh_user
  ssh_public_key_path = var.ssh_public_key_path
  user_data_path = coalesce(var.user_data_path, "${path.module}/cloud-init.yaml")
  create_public_ip = true
  labels = var.labels
}
module "s3_backups" {
  source = "./modules/S3"
  folder_id = var.folder_id
  bucket_name = var.backup_bucket_name
  service_account_name = var.backup_sa_name
  backup_retention_days = var.backup_retention_days
  versioning_enabled = var.backup_versioning_enabled
  labels = var.labels
  admin_access_key = yandex_iam_service_account_static_access_key.storage_admin.access_key
  admin_secret_key = yandex_iam_service_account_static_access_key.storage_admin.secret_key
}