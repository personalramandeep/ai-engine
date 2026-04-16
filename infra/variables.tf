variable "region" {
  default = "ap-south-1"
}

variable "service_name" {
  default = "kreeda-ai-engine"
}

variable "image_tag" {
  description = "Docker image tag to deploy (passed from CI)"
  type        = string
  default     = "latest"
}
