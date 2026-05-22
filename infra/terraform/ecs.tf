# Apex API as Fargate services in each region behind an ALB.

resource "aws_ecs_cluster" "primary" {
  provider = aws.primary
  name     = "${var.project}-primary"
  tags     = local.tags
}

resource "aws_ecs_cluster" "secondary" {
  provider = aws.secondary
  name     = "${var.project}-secondary"
  tags     = local.tags
}

resource "aws_ecs_task_definition" "api_primary" {
  provider                 = aws.primary
  family                   = "${var.project}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "4096"
  container_definitions = jsonencode([
    {
      name        = "api"
      image       = "ghcr.io/example/apex-rag/apex-api:latest"
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "POSTGRES_HOST", value = aws_db_instance.primary.address },
        { name = "VECTOR_STORE_DRIVER", value = "pgvector" }
      ]
    }
  ])
  tags = local.tags
}

resource "aws_ecs_service" "api_primary" {
  provider                          = aws.primary
  name                              = "${var.project}-api"
  cluster                           = aws_ecs_cluster.primary.id
  task_definition                   = aws_ecs_task_definition.api_primary.arn
  desired_count                     = 3
  launch_type                       = "FARGATE"
  health_check_grace_period_seconds = 30
  network_configuration {
    subnets          = aws_subnet.primary[*].id
    assign_public_ip = false
  }
  tags = local.tags
}
