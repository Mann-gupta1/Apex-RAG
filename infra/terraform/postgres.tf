# Postgres + pgvector in both regions: primary in `us-east-1`,
# cross-region read replica in `us-west-2`.

resource "random_password" "db" {
  length  = 28
  special = false
}

resource "aws_db_subnet_group" "primary" {
  provider   = aws.primary
  name       = "${var.project}-pg-primary"
  subnet_ids = aws_subnet.primary[*].id
  tags       = local.tags
}

resource "aws_db_subnet_group" "secondary" {
  provider   = aws.secondary
  name       = "${var.project}-pg-secondary"
  subnet_ids = aws_subnet.secondary[*].id
  tags       = local.tags
}

resource "aws_db_instance" "primary" {
  provider                = aws.primary
  identifier              = "${var.project}-pg-primary"
  engine                  = "postgres"
  engine_version          = "16.3"
  instance_class          = "db.r6g.large"
  allocated_storage       = 100
  storage_type            = "gp3"
  storage_encrypted       = true
  username                = "apex"
  password                = random_password.db.result
  db_name                 = "apex_rag"
  multi_az                = true
  backup_retention_period = 14
  deletion_protection     = true
  db_subnet_group_name    = aws_db_subnet_group.primary.name
  vpc_security_group_ids  = [aws_security_group.db_primary.id]
  parameter_group_name    = aws_db_parameter_group.pg.name
  tags                    = local.tags
}

resource "aws_db_instance" "replica" {
  provider               = aws.secondary
  identifier             = "${var.project}-pg-replica"
  replicate_source_db    = aws_db_instance.primary.arn
  instance_class         = "db.r6g.large"
  storage_encrypted      = true
  db_subnet_group_name   = aws_db_subnet_group.secondary.name
  vpc_security_group_ids = [aws_security_group.db_secondary.id]
  tags                   = local.tags
}

resource "aws_db_parameter_group" "pg" {
  provider = aws.primary
  name     = "${var.project}-pg-params"
  family   = "postgres16"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements,vector"
    apply_method = "pending-reboot"
  }
  parameter {
    name  = "log_min_duration_statement"
    value = "500"
  }
  tags = local.tags
}

# placeholder VPC + sg objects defined in vpc.tf for the documented topology
