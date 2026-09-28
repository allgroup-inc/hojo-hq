# KAKEHASHI APO PoC - Deployment Guide

This document describes the deployment process for the KAKEHASHI APO PoC application using Docker, Docker Compose, and Terraform.

## Architecture Overview

The deployment consists of:
- **Frontend**: React SPA served by Nginx (port 80)
- **Backend**: Node.js Express API (port 3000)
- **Database**: PostgreSQL 15 (port 5432)
- **Infrastructure**: AWS EC2 + RDS managed via Terraform

## Local Development (Docker Compose)

### Prerequisites
- Docker Desktop or Docker Engine 20.10+
- Docker Compose 2.0+
- Git

### Quick Start

1. Clone the repository:
```bash
git clone https://github.com/allgroup-inc/hojo-hq.git
cd hojo-hq
```

2. Create environment file:
```bash
cp docker-compose.example.env .env
# Edit .env with your configuration
```

3. Build and start containers:
```bash
docker-compose build
docker-compose up -d
```

4. Verify containers are running:
```bash
docker-compose ps
curl http://localhost/health
curl http://localhost:3000/health
```

5. View logs:
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db
```

6. Stop containers:
```bash
docker-compose down
```

### Environment Variables

Create `.env` file in project root:

```env
DB_USER=kakehashi
DB_PASSWORD=secure-password
DB_NAME=kakehashi_apo_poc
NODE_ENV=production
PORT=3000
ENTRA_CLIENT_ID=your-client-id
ENTRA_CLIENT_SECRET=your-client-secret
ENTRA_CALLBACK_URL=http://localhost:3000/auth/callback
```

### Database Access

Connect to PostgreSQL:
```bash
docker-compose exec db psql -U kakehashi -d kakehashi_apo_poc
```

### Troubleshooting

**Containers won't start:**
```bash
docker-compose logs
docker system prune -a  # Clean up dangling images
docker-compose build --no-cache
```

**Port conflicts:**
```bash
# Change ports in docker-compose.yml
# Or kill processes using ports:
lsof -i :80
lsof -i :3000
lsof -i :5432
```

**Database won't initialize:**
```bash
docker-compose down -v  # Remove volumes
docker-compose up -d
```

## Production Deployment (Terraform + AWS)

### Prerequisites
- AWS Account with appropriate IAM permissions
- Terraform 1.6.0+
- AWS CLI configured with credentials

### Setup

1. Configure AWS credentials:
```bash
aws configure
# Or set environment variables:
export AWS_ACCESS_KEY_ID=your-key-id
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_DEFAULT_REGION=ap-northeast-1
```

2. Initialize Terraform:
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform init
```

3. Review Terraform plan:
```bash
terraform plan -out=tfplan
```

4. Apply Terraform configuration:
```bash
terraform apply tfplan
```

### Terraform Variables

Edit `terraform/terraform.tfvars`:

```hcl
aws_region          = "ap-northeast-1"  # AWS region
instance_type       = "t3.large"        # EC2 instance type
db_instance_class   = "db.t3.micro"     # RDS instance type
db_name             = "kakehashi_apo_poc"
db_username         = "kakehashi"
db_password         = "CHANGE_ME_IN_PRODUCTION"  # MUST change this!
docker_registry     = ""                # Optional: Docker registry URL
```

### AWS Resources Created

- **VPC**: 10.0.0.0/16 with public and private subnets
- **EC2**: Application server with Docker and Docker Compose
- **RDS**: PostgreSQL 15 database with automated backups
- **Security Groups**: Configured for HTTP/HTTPS/API access
- **Elastic IP**: Static IP for application server
- **IAM**: Optional instance profile for AWS service access

### Post-Deployment

After Terraform apply completes:

1. Get outputs:
```bash
terraform output app_public_ip
terraform output db_address
```

2. SSH to EC2 instance:
```bash
ssh -i your-key-pair.pem ubuntu@<app_public_ip>
```

3. Check deployment status:
```bash
docker-compose ps
docker-compose logs
```

4. Access application:
- Frontend: http://<app_public_ip>
- API: http://<app_public_ip>:3000
- Health: http://<app_public_ip>:3000/health

### Infrastructure Maintenance

**Scale up database:**
```hcl
# In terraform.tfvars
db_instance_class = "db.t3.small"  # or larger
terraform apply
```

**Update EC2 instance type:**
```hcl
# In terraform.tfvars
instance_type = "t3.xlarge"
terraform apply
```

**Destroy infrastructure (WARNING: Irreversible):**
```bash
terraform destroy
# You'll be prompted to confirm
```

### Backup and Recovery

**Automated backups:**
- RDS has 7-day backup retention
- Daily snapshots at 03:00-04:00 JST
- Maintenance window: Monday 04:00-05:00 JST

**Manual snapshot:**
```bash
aws rds create-db-snapshot \
  --db-instance-identifier kakehashi-apo-db \
  --db-snapshot-identifier kakehashi-snapshot-$(date +%s)
```

**Restore from snapshot:**
```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier kakehashi-apo-db-restored \
  --db-snapshot-identifier kakehashi-snapshot-1234567890
```

## CI/CD Pipeline

GitHub Actions workflow: `.github/workflows/deploy-poc.yml`

Triggered on:
- Push to `claude/sales-appointment-management-app-5fuo4y` branch
- Changes to `apps/kakehashi-apo-poc/`, `docker-compose.yml`, or `terraform/`

Jobs:
1. **test**: Unit tests, integration tests, Docker build
2. **lint-terraform**: Terraform format and validation
3. **security-scan**: Trivy image scanning for vulnerabilities
4. **deploy-plan**: Terraform plan (no actual deployment)

### Manual Deployment via GitHub Actions

1. Push code to the branch
2. Workflow runs automatically
3. Review build and plan results
4. Manual Terraform apply (if needed):
```bash
cd terraform
terraform apply tfplan
```

## Security Considerations

1. **Secrets Management**:
   - Use AWS Secrets Manager for sensitive data
   - Never commit `.env` or `terraform.tfvars` with real values
   - Rotate credentials regularly

2. **Network Security**:
   - Security groups restrict access to necessary ports
   - RDS only accessible from EC2
   - Public subnet only for EC2 (optional Bastion host for management)

3. **Database**:
   - PostgreSQL password must be changed from default
   - Enable SSL for connections in production
   - Regular backups enabled (7-day retention)

4. **Container Security**:
   - Non-root user in containers (nodejs:1001)
   - Multi-stage Docker builds to minimize image size
   - Regular dependency updates via npm audit

5. **Access Control**:
   - IAM roles for EC2 if AWS API access needed
   - SSH key pair for EC2 access
   - VPC-level network isolation

## Monitoring and Logging

### Container Logs
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db
```

### AWS CloudWatch (Optional)
```bash
# Install CloudWatch agent on EC2
aws ssm send-command \
  --document-name "AWS-ConfigureAWSPackage" \
  --parameters "action=Install,name=AmazonCloudWatchAgent" \
  --instance-ids "i-xxxxxxxxx"
```

### Application Monitoring
- Health endpoints: `/health`
- API metrics: `/metrics` (if Prometheus added)
- Database: CloudWatch RDS metrics

## Scaling and Performance

### Vertical Scaling (Larger Instances)
```hcl
# Increase instance size
instance_type = "t3.xlarge"
terraform apply
```

### Horizontal Scaling (Multiple EC2 instances)
1. Create load balancer (ALB)
2. Add auto-scaling group
3. Register multiple EC2 instances
(Not included in basic PoC setup)

### Database Performance
- Monitor RDS Performance Insights
- Enable read replicas if needed
- Optimize queries based on logs

## Rollback Procedures

### Docker Compose
```bash
docker-compose down
docker-compose up -d  # Restart previous version
```

### Terraform
```bash
# View previous state
terraform state list

# Restore previous state
terraform state push terraform.tfstate.backup

# Or destroy and reapply
terraform destroy
terraform apply
```

## Troubleshooting

### Common Issues

**Application won't start:**
```bash
docker-compose logs backend
# Check environment variables in .env
# Verify database connectivity
```

**Database connection error:**
```bash
# Check PostgreSQL status
docker-compose exec db psql -U kakehashi -d kakehashi_apo_poc -c "SELECT 1"

# Check network connectivity
docker-compose exec backend nc -zv db 5432
```

**Frontend not loading:**
```bash
# Check Nginx logs
docker-compose logs frontend

# Verify API connectivity
curl -v http://localhost:3000/health
```

**Terraform state corruption:**
```bash
# Backup current state
cp terraform.tfstate terraform.tfstate.backup

# Refresh state
terraform refresh

# Or reinitialize
rm -rf .terraform
terraform init
```

### Support

For issues, check:
1. Logs: `docker-compose logs` or AWS CloudWatch
2. GitHub Issues: https://github.com/allgroup-inc/hojo-hq/issues
3. Documentation: This file and docs/ directory

## Additional Resources

- Docker Documentation: https://docs.docker.com/
- Docker Compose: https://docs.docker.com/compose/
- Terraform AWS Provider: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- AWS RDS: https://docs.aws.amazon.com/rds/
- PostgreSQL: https://www.postgresql.org/docs/

---

Last updated: 2026-09-28
Maintained by: KAKEHASHI APO Team
