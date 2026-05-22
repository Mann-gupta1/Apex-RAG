# Minimal per-region VPC + subnets + security groups.
# This file is intentionally compact; a real engagement would split into modules.

resource "aws_vpc" "primary" {
  provider             = aws.primary
  cidr_block           = "10.10.0.0/16"
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = "${var.project}-vpc-primary" })
}

resource "aws_vpc" "secondary" {
  provider             = aws.secondary
  cidr_block           = "10.20.0.0/16"
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = "${var.project}-vpc-secondary" })
}

data "aws_availability_zones" "primary"   { provider = aws.primary   }
data "aws_availability_zones" "secondary" { provider = aws.secondary }

resource "aws_subnet" "primary" {
  provider                = aws.primary
  count                   = 3
  vpc_id                  = aws_vpc.primary.id
  cidr_block              = cidrsubnet(aws_vpc.primary.cidr_block, 4, count.index)
  availability_zone       = data.aws_availability_zones.primary.names[count.index]
  map_public_ip_on_launch = false
  tags                    = merge(local.tags, { Name = "${var.project}-primary-${count.index}" })
}

resource "aws_subnet" "secondary" {
  provider                = aws.secondary
  count                   = 3
  vpc_id                  = aws_vpc.secondary.id
  cidr_block              = cidrsubnet(aws_vpc.secondary.cidr_block, 4, count.index)
  availability_zone       = data.aws_availability_zones.secondary.names[count.index]
  map_public_ip_on_launch = false
  tags                    = merge(local.tags, { Name = "${var.project}-secondary-${count.index}" })
}

resource "aws_security_group" "db_primary" {
  provider    = aws.primary
  name        = "${var.project}-db-primary"
  description = "Postgres ingress from API tasks"
  vpc_id      = aws_vpc.primary.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}

resource "aws_security_group" "db_secondary" {
  provider    = aws.secondary
  name        = "${var.project}-db-secondary"
  description = "Postgres ingress from API tasks"
  vpc_id      = aws_vpc.secondary.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = local.tags
}
