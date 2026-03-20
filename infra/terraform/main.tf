terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "watchflow-terraform-state"
    key            = "production/api.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "watchflow-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
}

# --- RDS PostgreSQL ---
resource "aws_db_instance" "postgres" {
  identifier        = "watchflow-${var.environment}"
  engine            = "postgres"
  engine_version    = "16.2"
  instance_class    = var.db_instance_class
  allocated_storage = 100
  storage_type      = "gp3"
  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn

  db_name  = "watchflow"
  username = "watchflow"
  password = var.db_password  # sourced from Secrets Manager via Terraform Cloud workspace var

  multi_az               = var.environment == "production"
  deletion_protection    = var.environment == "production"
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "mon:04:00-mon:05:00"

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  performance_insights_enabled = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  tags = local.common_tags
}

# --- ElastiCache Redis ---
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "watchflow-${var.environment}"
  description          = "Watchflow Redis"
  node_type            = "cache.t4g.small"
  num_cache_clusters   = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  security_group_ids   = [aws_security_group.redis.id]
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  tags = local.common_tags
}

# --- ECS Cluster ---
resource "aws_ecs_cluster" "main" {
  name = "watchflow-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.common_tags
}

# --- KMS Keys ---
resource "aws_kms_key" "rds" {
  description             = "Watchflow RDS encryption key"
  deletion_window_in_days = 14
  enable_key_rotation     = true
  tags                    = local.common_tags
}

resource "aws_kms_key" "secrets" {
  description             = "Watchflow Secrets Manager encryption key"
  deletion_window_in_days = 14
  enable_key_rotation     = true
  tags                    = local.common_tags
}

# --- Secrets Manager ---
resource "aws_secretsmanager_secret" "app_secrets" {
  name       = "watchflow/${var.environment}"
  kms_key_id = aws_kms_key.secrets.arn
  tags       = local.common_tags
}

locals {
  common_tags = {
    Project     = "watchflow"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
