output "bucket_name" {
  value = yandex_storage_bucket.this.bucket
}

output "bucket_domain_name" {
  value = yandex_storage_bucket.this.bucket_domain_name
}

output "service_account_id" {
  value = yandex_iam_service_account.this.id
}

output "access_key" {
  value     = yandex_iam_service_account_static_access_key.this.access_key
  sensitive = true
}

output "secret_key" {
  value     = yandex_iam_service_account_static_access_key.this.secret_key
  sensitive = true
}
