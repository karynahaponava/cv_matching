variable "image_family" {
    type    = string
    default = "ubuntu-2204-lts"
}
variable "create_public_ip" {
    type    = bool
    default = true
}
variable "instance_name" {
    type    = string
}
variable "folder_id" {
    type = string 
}
variable "zone" {
    type = string  
}
variable "hostname" {
    type = string
    default = null
}
variable "platform_id" {
    type = string
    default = "standard-v3"   
}
variable "labels" {
  type = map(string)
  default = {}
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
variable "boot_disk_type" {
  type = string
  default = "network-ssd"
}
variable "subnet_id" {
    type = string
}
variable "security_group_ids" {
    type = list(string)
    default = [] 
}
variable "ssh_public_key_path" {
    type = string
}
variable "ssh_user" {
    type = string
    default = "ubuntu" 
}
variable "preemptible" {
  type = bool
  default = false
}
variable "user_data_path" {
    type    = string
    default = null
}