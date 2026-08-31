variable "yc_token" {
    type = string
    sensitive = true
}
variable "cloud_id" {
    type = string
}
variable "folder_id" {
    type = string
}
variable "zone" {
    type = string
    default = "ru-central1-a"
}
variable "instance_name" {
    type = string
    default = "cv-matching-vm"
}
variable "subnet_id" {
    type = string
}
variable "security_group_ids" {
    type = list(string)
    default = []
}
variable "cores" {
    type = number
    default = 2
}
variable "memory" {
    type = number
    default = 4
}
variable "core_fraction" {
    type = number
    default = 100
}
variable "boot_disk_size" {
    type = number
    default = 30
}
variable "ssh_user" {
    type = string
    default = "ubuntu"
}
variable "ssh_public_key_path" {
    type = string
    default = "~/.ssh/id_rsa.pub"
}
variable "user_data_path" {
    type    = string
    default = null
}
variable "labels" {
    type = map(string)
    default = {
        project = "cv-matching"
        env = "prod"
    }
}
variable "backup_bucket_name" {
    type = string
}
variable "backup_sa_name" {
    type    = string
    default = "cv-matching-backup-sa"
}
variable "backup_retention_days" {
    type    = number
    default = 30
}
variable "backup_versioning_enabled" {
    type    = bool
    default = true
}