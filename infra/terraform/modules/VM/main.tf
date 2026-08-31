data "yandex_compute_image" "this" {
  family = var.image_family
}
resource "yandex_vpc_address" "this" {
  count = var.create_public_ip ? 1 : 0
  name  = "${var.instance_name}-public-ip"
  folder_id = var.folder_id
  external_ipv4_address {
    zone_id = var.zone
  }
}
resource "yandex_compute_instance" "this" {
    name = var.instance_name
    folder_id = var.folder_id
    zone = var.zone
    hostname = var.hostname
    platform_id = var.platform_id
    labels = var.labels
    resources {
        cores = var.cores
        memory = var.memory
        core_fraction = var.core_fraction
    }
    boot_disk {
        initialize_params {
            image_id = data.yandex_compute_image.this.id
            size = var.boot_disk_size
            type = var.boot_disk_type
        }
    }
    network_interface {
        subnet_id = var.subnet_id
        security_group_ids = var.security_group_ids
        nat = var.create_public_ip
        nat_ip_address = try(yandex_vpc_address.this[0].external_ipv4_address[0].address, null)
    }
    metadata = {
        ssh-keys = "${var.ssh_user}:${file(var.ssh_public_key_path)}"
        user-data = try(file(var.user_data_path), null)
    }
    scheduling_policy {
        preemptible = var.preemptible
  }
}