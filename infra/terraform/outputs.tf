output "instance_id" {
    value = module.vm.instance_id
}
output "public_ip"{
    value = module.vm.public_ip
}
output "private_ip" {
    value = module.vm.private_ip
}
output "fqdn" {
    value = module.vm.fqdn
}
output "backup_bucket_name" {
    value = module.s3_backups.bucket_name
}
output "backup_bucket_domain" {
    value = module.s3_backups.bucket_domain_name
}
output "backup_access_key" {
    value     = module.s3_backups.access_key
    sensitive = true
}
output "backup_secret_key" {
    value     = module.s3_backups.secret_key
    sensitive = true
}