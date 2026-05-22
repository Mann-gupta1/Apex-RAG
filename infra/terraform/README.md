# Apex RAG — Multi-Region Infrastructure (Documented Reference)

> This Terraform is **documented and version-controlled but intentionally not
> applied** in the local build. It exists to demonstrate the production
> topology described in the system-design layer of the spec.

## Topology

```
                ┌──────────────────────────────┐
                │       Cloudflare / R2        │
                │  (CDN, WAF, mTLS termination)│
                └────────────────┬─────────────┘
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                                                  │
┌───────▼─────────┐                                ┌───────▼─────────┐
│  us-east-1      │                                │   us-west-2     │
│  ┌───────────┐  │   logical replication          │  ┌───────────┐  │
│  │  PG-PRIMARY│◀─┼──────────────────────────────▶│  │ PG-REPLICA │  │
│  │  pgvector  │  │                                │  │ pgvector   │  │
│  └─────▲─────┘  │                                └─────▲─────────┘  │
│        │ writes │                                       │ reads     │
│  ┌─────┴─────┐  │                                ┌─────┴─────────┐  │
│  │  apex-api │  │                                │  apex-api      │  │
│  │  (ECS/Fargate)                                │  (ECS/Fargate)  │  │
│  └─────▲─────┘  │                                └─────▲─────────┘  │
└────────┼────────┘                                ──────┼────────────┘
         │                                               │
         └────────────── Route 53 / latency-based ───────┘
```

## Files

- `main.tf` — top-level providers, remote state.
- `vpc.tf` — VPC + subnets per region (3 AZs).
- `postgres.tf` — RDS Postgres 16 with `pgvector`, multi-AZ in primary,
  cross-region read replica in secondary.
- `redis.tf` — ElastiCache Redis 7 with replication groups in each region.
- `ecs.tf` — Fargate services + ALB for the API.
- `route53.tf` — latency-based DNS, weighted records.
- `iam.tf` — task roles, KMS key for Phoenix traces.

## How writes work

- Writes always hit the primary region (`us-east-1`).
- The secondary region's API points read traffic at its local Postgres
  replica, but writes are forwarded via Route 53's `apex-write.internal`
  CNAME, which resolves to the primary's ALB.
- Replication lag is monitored via CloudWatch + Phoenix custom span attribute
  (`pg.replica_lag_seconds`); a sustained value > 30 s pages on-call.

## Why this isn't applied locally

- No cloud spend; the project must run free.
- We keep the Terraform reviewable and lintable (`terraform validate`).
- A reviewer reading the case study can verify the architecture without us
  provisioning anything.

## When to enable

If you adopt Apex RAG inside a real engagement, copy `terraform.tfvars.example`
to `terraform.tfvars`, fill in the AWS account ids, and:

```bash
terraform init
terraform plan
terraform apply
```
