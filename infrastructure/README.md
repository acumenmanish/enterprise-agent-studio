# Infrastructure

Terraform + Kubernetes manifests for DEV/STAGING/PROD on AWS EKS.

**Not started.** Needs from you before this can begin:
- AWS account/org structure and which account(s) map to DEV/STAGING/PROD
- Whether EKS is confirmed or you want to evaluate ECS Fargate instead
  (see architecture critique — EKS carries real ops overhead for a
  5-person team at 3-tenant pilot scale)
- Terraform state backend (S3 + DynamoDB lock table) location
