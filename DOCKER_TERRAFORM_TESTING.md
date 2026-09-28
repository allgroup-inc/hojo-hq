# Docker & Terraform Testing Guide for KAKEHASHI APO PoC

## Pre-requisites

- Docker Desktop/Engine 20.10+ with Docker Compose 2.0+
- Terraform 1.6.0+
- AWS CLI (for production deployment)
- Node.js 20+ (for local development, optional)
- Git

## Part 1: Local Development with Docker Compose

### 1.1 Build Docker Images

```bash
cd /home/user/hojo-hq

# Build all services
docker-compose build

# Expected output:
# [+] Building 123.4s (XX/XX)
# ...
# Successfully built kakehashi-apo-backend:latest
# Successfully built kakehashi-apo-frontend:latest
```

### 1.2 Start Services

```bash
# Start all containers in background
docker-compose up -d

# Expected output:
# [+] Running 4/4
# ✔ Network kakehashi-apo_default  Created
# ✔ Container kakehashi-apo-db      Healthy
# ✔ Container kakehashi-apo-backend Healthy
# ✔ Container kakehashi-apo-frontend Healthy
```

### 1.3 Verify Services

```bash
# Check container status
docker-compose ps

# Expected output shows all containers RUNNING with status "Healthy" or "Up"
```

### 1.4 Test Endpoints

```bash
# Test backend health endpoint
curl -v http://localhost:3000/health
# Expected: HTTP 200 OK

# Test frontend
curl -v http://localhost/
# Expected: HTTP 200 OK with HTML content

# Test backend API availability
curl -v http://localhost:3000/
# Expected: HTTP 200 or 404 (API endpoint availability)

# Check Nginx health (frontend container)
curl -v http://localhost/health
# Expected: HTTP 200 OK with "healthy" response
```

### 1.5 Database Connectivity Test

```bash
# Connect to PostgreSQL
docker-compose exec db psql -U kakehashi -d kakehashi_apo_poc -c "SELECT 1;"
# Expected output:
#  ?column?
# ----------
#         1

# Test from backend container
docker-compose exec backend node -e "
  const PG = require('pg');
  const pool = new PG.Pool({
    connectionString: process.env.DATABASE_URL
  });
  pool.query('SELECT NOW()', (err, res) => {
    if (err) console.error('Error:', err);
    else console.log('Connected:', res.rows);
    process.exit(err ? 1 : 0);
  });
"
# Expected: Connection successful message
```

### 1.6 View Logs

```bash
# Backend logs
docker-compose logs -f backend --tail=50

# Frontend logs  
docker-compose logs -f frontend --tail=50

# Database logs
docker-compose logs -f db --tail=50

# All logs
docker-compose logs -f
```

### 1.7 Run Tests Inside Containers

```bash
# Backend unit tests
docker-compose exec backend npm run test

# Backend integration tests
docker-compose exec backend npm run test:integration

# Frontend tests
docker-compose exec frontend npm run test -- --coverage --watchAll=false

# Frontend E2E tests (if available)
docker-compose exec frontend npm run test:e2e
```

### 1.8 Performance Testing

```bash
# Check resource usage
docker stats

# Load test endpoint (requires ab or siege)
ab -n 100 -c 10 http://localhost/health

# Or using curl with time measurement
time curl -s http://localhost/health > /dev/null
```

### 1.9 Cleanup

```bash
# Stop containers (keep volumes)
docker-compose stop

# Stop and remove containers
docker-compose down

# Remove everything including volumes (WARNING: deletes data)
docker-compose down -v

# Remove images
docker-compose down --rmi all
```

## Part 2: Terraform Validation and Syntax Checking

### 2.1 Format Checking

```bash
cd terraform

# Check Terraform formatting
terraform fmt -check -recursive

# Auto-fix formatting issues
terraform fmt -recursive

# Expected: No output or lists files that were reformatted
```

### 2.2 Syntax Validation

```bash
# Initialize Terraform (local, no backend)
terraform init -backend=false

# Expected output:
# Terraform has been successfully configured!
# No changes. No remote state was pulled.

# Validate configuration
terraform validate

# Expected output:
# Success! The configuration is valid.
```

### 2.3 Terraform Plan (Dry Run)

```bash
# Copy example variables
cp terraform.tfvars.example terraform.tfvars

# Edit with test values (DO NOT use production passwords)
# vim terraform.tfvars

# Initialize with backend (for plan)
terraform init

# Create plan file
terraform plan -out=tfplan

# Expected output:
# Plan: X to add, Y to change, Z to destroy
```

### 2.4 Inspect Plan

```bash
# Show plan in human-readable format
terraform show tfplan | head -100

# Save plan to JSON for analysis
terraform show -json tfplan > plan.json

# Check specific resource
terraform show tfplan | grep "aws_instance"
```

### 2.5 Security Review

```bash
# Check for hardcoded secrets (basic)
grep -r "password\|secret\|key" terraform/ --include="*.tf" | grep -v "tfvars.example"

# Use tfsec for security scanning (if installed)
tfsec terraform/ --format json

# Check IAM policies (if present)
grep -r "aws_iam" terraform/
```

## Part 3: AWS Deployment (Production)

### 3.1 Pre-Deployment Checklist

```bash
# Verify AWS credentials are configured
aws sts get-caller-identity
# Should return: Account, UserId, Arn

# Check AWS region
aws configure list
# Should show correct region (ap-northeast-1)

# Verify IAM permissions
aws ec2 describe-vpcs --max-results 1
# Should succeed if you have EC2 permissions
```

### 3.2 Production Deployment

```bash
cd terraform

# Copy and update production values
cp terraform.tfvars.example terraform.tfvars

# IMPORTANT: Change all values to production settings
# - Use strong db_password (minimum 32 characters)
# - Set correct AWS region
# - Use appropriate instance types for workload
# vim terraform.tfvars

# Initialize with backend (optional, for state management)
terraform init

# Create plan
terraform plan -out=tfplan -var-file=terraform.tfvars

# Review plan carefully
terraform show tfplan | head -200

# Apply infrastructure
terraform apply tfplan

# Expected output after ~10-15 minutes:
# Apply complete! Resources: 10 added, 0 changed, 0 destroyed.
# Outputs:
# app_public_ip = "xxx.xxx.xxx.xxx"
# db_address = "kakehashi-apo-db.c..."
```

### 3.3 Post-Deployment Verification

```bash
# Get outputs
terraform output app_public_ip
terraform output app_public_dns
terraform output db_address

# SSH to EC2 (may take 5 minutes for init.sh to complete)
SSH_KEY="your-keypair.pem"
APP_IP=$(terraform output -raw app_public_ip)
ssh -i $SSH_KEY ubuntu@$APP_IP

# On EC2 instance, verify deployment
sudo docker-compose ps
sudo docker-compose logs

# Test from local machine
curl http://<app_public_ip>/health
curl http://<app_public_ip>:3000/health

# Wait for application startup (5-10 minutes)
watch -n 5 "curl -s http://<app_public_ip>/health"
```

### 3.4 Destroy Infrastructure

```bash
# WARNING: This destroys all resources and data!

# Create snapshot before destroying (recommended)
SNAPSHOT_ID=$(date +%s)
aws rds create-db-snapshot \
  --db-instance-identifier kakehashi-apo-db \
  --db-snapshot-identifier kakehashi-backup-$SNAPSHOT_ID

# Destroy infrastructure
terraform destroy -var-file=terraform.tfvars

# Confirm when prompted: type "yes"

# Expected output:
# Destroy complete! Resources: 10 destroyed.
```

## Part 4: Integration Testing

### 4.1 End-to-End Test (Local)

```bash
# Start services
docker-compose up -d

# Wait for services to be healthy
sleep 10

# Test workflow
echo "Testing E2E workflow..."

# 1. Check database
echo "1. Testing database..."
docker-compose exec db psql -U kakehashi -d kakehashi_apo_poc -c "SELECT 1;" || exit 1

# 2. Check backend
echo "2. Testing backend..."
curl -f http://localhost:3000/health || exit 1

# 3. Check frontend
echo "3. Testing frontend..."
curl -f http://localhost/health || exit 1

# 4. Run backend tests
echo "4. Running backend tests..."
docker-compose exec backend npm run test:integration || exit 1

echo "All tests passed!"
docker-compose down
```

### 4.2 Terraform State Testing

```bash
cd terraform

# Verify state file exists and is valid
terraform validate

# List resources in state
terraform state list

# Show specific resource details
terraform state show aws_instance.kakehashi_app

# Plan changes (should show "No changes")
terraform plan -var-file=terraform.tfvars
```

### 4.3 Security Testing

```bash
# Check for exposed secrets in code
git log -p --all -S "password\|secret\|key" | head -100

# Scan container images (requires trivy)
docker scan kakehashi-apo-backend:latest
docker scan kakehashi-apo-frontend:latest

# Check Dockerfile best practices
docker run --rm -i hadolint/hadolint < apps/kakehashi-apo-poc/backend/Dockerfile
docker run --rm -i hadolint/hadolint < apps/kakehashi-apo-poc/frontend/Dockerfile
```

## Part 5: Troubleshooting

### Common Issues and Solutions

#### Docker Compose Issues

**Issue**: `docker: command not found`
```bash
# Solution: Install Docker Desktop or Docker Engine
# For Linux:
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

**Issue**: `Bind for 0.0.0.0:80 failed: port is already allocated`
```bash
# Solution: Change ports in docker-compose.yml or kill existing process
lsof -i :80
kill -9 <PID>
# Or change port in docker-compose.yml to 8080:80
```

**Issue**: Database connection fails
```bash
# Solution: Ensure DB is healthy first
docker-compose ps db
# Wait for "Healthy" status
docker-compose logs db
```

#### Terraform Issues

**Issue**: `terraform: command not found`
```bash
# Solution: Install Terraform
# macOS: brew install terraform
# Linux: 
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

**Issue**: `Error: Invalid AWS region`
```bash
# Solution: Set correct region
export AWS_DEFAULT_REGION=ap-northeast-1
# Or update terraform.tfvars
```

**Issue**: `Error: creating EC2 Instance: UnauthorizedOperation`
```bash
# Solution: Check AWS credentials and IAM permissions
aws sts get-caller-identity
# Verify IAM policy includes ec2:*, rds:*, vpc:* actions
```

## Part 6: Monitoring and Logs

### Local Monitoring

```bash
# Real-time metrics
docker stats

# Container events
docker events --filter type=container

# Network inspection
docker network inspect kakehashi-apo_default
```

### AWS CloudWatch Monitoring

```bash
# View RDS metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBInstanceIdentifier,Value=kakehashi-apo-db \
  --start-time 2026-09-28T00:00:00Z \
  --end-time 2026-09-28T23:59:59Z \
  --period 3600 \
  --statistics Average

# View EC2 metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/EC2 \
  --metric-name CPUUtilization \
  --dimensions Name=InstanceId,Value=i-xxxxx \
  --start-time 2026-09-28T00:00:00Z \
  --end-time 2026-09-28T23:59:59Z \
  --period 300 \
  --statistics Average
```

## Test Results Checklist

- [ ] Docker images build successfully
- [ ] All containers start and reach "Healthy" state
- [ ] Backend API responds to health check
- [ ] Frontend loads in browser
- [ ] Database accepts connections
- [ ] Backend can connect to database
- [ ] Unit tests pass (backend)
- [ ] Integration tests pass (backend)
- [ ] Frontend tests pass
- [ ] E2E tests pass (if available)
- [ ] Terraform validates without errors
- [ ] Terraform plan shows expected resources
- [ ] Security scanning finds no critical issues
- [ ] Logs show no error messages during startup
- [ ] Performance tests meet requirements
- [ ] Cleanup operations work correctly

## Success Criteria

✅ All tests pass  
✅ No security vulnerabilities in scan results  
✅ Resources deploy within expected time  
✅ Application is accessible at configured endpoints  
✅ Database backups are functioning  
✅ Monitoring and logging are operational  

---

For detailed deployment instructions, see DEPLOYMENT.md
