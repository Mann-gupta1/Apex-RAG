# Latency-based DNS for read traffic, single-target CNAME for writes.

data "aws_route53_zone" "main" {
  provider = aws.primary
  name     = "example.internal."
  private_zone = true
}

resource "aws_route53_record" "api_primary" {
  provider       = aws.primary
  zone_id        = data.aws_route53_zone.main.zone_id
  name           = "apex-api"
  type           = "CNAME"
  ttl            = 60
  set_identifier = "primary"
  latency_routing_policy { region = var.primary_region }
  records = ["primary-api.${var.primary_region}.elb.amazonaws.com"]
}

resource "aws_route53_record" "api_secondary" {
  provider       = aws.secondary
  zone_id        = data.aws_route53_zone.main.zone_id
  name           = "apex-api"
  type           = "CNAME"
  ttl            = 60
  set_identifier = "secondary"
  latency_routing_policy { region = var.secondary_region }
  records = ["secondary-api.${var.secondary_region}.elb.amazonaws.com"]
}
