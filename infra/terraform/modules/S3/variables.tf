variable "service_account_name" {
    type = string
    default = "s3-backup-sa"
}
variable "folder_id" {
    type = string
}
variable "bucket_name" {
    type = string 
}
variable "labels" {
  type    = map(string)
  default = {}
}
variable "versioning_enabled" {
  type    = bool
  default = true
}
variable "backup_retention_days" {
    type = number
    default = 30
}
variable "noncurrent_version_expiration_days" {
    type = number
    default = 90
}
variable "admin_access_key" {
    type = string
    sensitive = true
}
variable "admin_secret_key" {
    type = string
    sensitive = true
}