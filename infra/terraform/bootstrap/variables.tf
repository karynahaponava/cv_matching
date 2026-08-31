variable "yc_token" {
  type      = string
  sensitive = true
}
variable "cloud_id" {
  type = string
}
variable "folder_id" {
  type = string
}
variable "zone" {
  type    = string
  default = "ru-central1-a"
}
variable "tfstate_bucket_name" {
  type    = string
  default = "cv-matching-tfstate"
}
variable "labels" {
  type = map(string)
  default = {
    project = "cv-matching"
    env     = "prod"
  }
}
