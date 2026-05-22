# Apex RAG — root terraform (documented reference, not applied).
# Run `terraform validate` to type-check.

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.40.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.6.0"
    }
  }

  # Remote state: documented but commented out so `terraform init` works locally.
  # backend "s3" {
  #   bucket         = "apex-rag-tfstate"
  #   key            = "infra/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "apex-rag-tflock"
  # }
}

variable "primary_region"   { type = string  default = "us-east-1" }
variable "secondary_region" { type = string  default = "us-west-2" }
variable "project"          { type = string  default = "apex-rag" }
variable "environment"      { type = string  default = "prod" }

provider "aws" {
  alias  = "primary"
  region = var.primary_region
}

provider "aws" {
  alias  = "secondary"
  region = var.secondary_region
}

locals {
  tags = {
    project     = var.project
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Outputs
output "primary_region"   { value = var.primary_region }
output "secondary_region" { value = var.secondary_region }
