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
