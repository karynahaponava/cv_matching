output "instance_id" {
  value = yandex_compute_instance.this.id
}
output "public_ip" {
  value = yandex_compute_instance.this.network_interface[0].nat_ip_address
}

output "private_ip" {
  value = yandex_compute_instance.this.network_interface[0].ip_address
}

output "fqdn" {
  value       = yandex_compute_instance.this.fqdn
}
