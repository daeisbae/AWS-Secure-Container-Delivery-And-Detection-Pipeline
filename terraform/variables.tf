variable "aws_region" {
  type    = string
  default = "ca-central-1"
}

variable "project_name" {
  type    = string
  default = "secure-container-pipeline"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,26}[a-z0-9]$", var.project_name)) && length(regexall("--", var.project_name)) == 0
    error_message = "project_name must be 3 to 28 lowercase letters, numbers, or hyphens; start with a letter; end with a letter or number; and contain no consecutive hyphens."
  }
}

variable "environment" {
  type    = string
  default = "lab"
}

variable "github_oidc_subject" {
  type = string

  validation {
    condition     = startswith(var.github_oidc_subject, "repo:") && !can(regex("[?*]", var.github_oidc_subject))
    error_message = "github_oidc_subject must start with repo: and contain no wildcards."
  }
}

variable "manage_github_oidc_provider" {
  type    = bool
  default = false
}

variable "allowed_cidr_blocks" {
  type    = list(string)
  default = []

  validation {
    condition     = alltrue([for cidr in var.allowed_cidr_blocks : try(cidrnetmask(cidr) == "255.255.255.255", false)])
    error_message = "Every allowed_cidr_blocks entry must be a valid IPv4 /32."
  }
}

variable "container_port" {
  type    = number
  default = 8000

  validation {
    condition     = var.container_port >= 1 && var.container_port <= 65535
    error_message = "container_port must be between 1 and 65535."
  }
}

variable "log_retention_days" {
  type    = number
  default = 14
}
