variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (staging | production)"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be 'staging' or 'production'"
  }
}

variable "db_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t4g.medium"
}

variable "db_password" {
  description = "RDS master password (sensitive — set via workspace variable)"
  type        = string
  sensitive   = true
}

variable "vpc_id" {
  description = "VPC ID for resource placement"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS tasks and RDS"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for ALB"
  type        = list(string)
}

variable "enable_deletion_protection" {
  description = "Enable RDS deletion protection. Defaults to true in production."
  type        = bool
  default     = null  # resolved dynamically in main.tf locals

  validation {
    condition     = var.enable_deletion_protection == null || can(tobool(var.enable_deletion_protection))
    error_message = "enable_deletion_protection must be a boolean or null."
  }
}

variable "backup_retention_days" {
  description = "RDS automated backup retention period (days). Min 1, max 35."
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 1 and 35."
  }
}
