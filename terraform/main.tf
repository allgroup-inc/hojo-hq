# AWS Provider
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC
resource "aws_vpc" "kakehashi_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true

  tags = {
    Name = "kakehashi-apo-vpc"
  }
}

# Public Subnet
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.kakehashi_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "kakehashi-apo-public-subnet"
  }
}

# Private Subnet for RDS
resource "aws_subnet" "private" {
  vpc_id            = aws_vpc.kakehashi_vpc.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.aws_region}b"

  tags = {
    Name = "kakehashi-apo-private-subnet"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "kakehashi_igw" {
  vpc_id = aws_vpc.kakehashi_vpc.id

  tags = {
    Name = "kakehashi-apo-igw"
  }
}

# Route Table for public subnet
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.kakehashi_vpc.id

  route {
    cidr_block      = "0.0.0.0/0"
    gateway_id      = aws_internet_gateway.kakehashi_igw.id
  }

  tags = {
    Name = "kakehashi-apo-public-rt"
  }
}

# Route Table Association
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Security Group
resource "aws_security_group" "kakehashi_sg" {
  name        = "kakehashi-apo-sg"
  description = "Security group for KAKEHASHI APO PoC"
  vpc_id      = aws_vpc.kakehashi_vpc.id

  # HTTP
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Backend API
  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # PostgreSQL (internal only)
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    security_groups = [aws_security_group.kakehashi_sg.id]
  }

  # Outbound
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "kakehashi-apo-sg"
  }
}

# EC2 Instance
resource "aws_instance" "kakehashi_app" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type

  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.kakehashi_sg.id]

  # Assign public IP
  associate_public_ip_address = true

  user_data = base64encode(templatefile("${path.module}/init.sh", {
    db_host     = aws_db_instance.postgres.address
    db_port     = aws_db_instance.postgres.port
    db_user     = var.db_username
    db_password = var.db_password
    db_name     = var.db_name
    docker_registry = var.docker_registry
  }))

  root_block_device {
    volume_type           = "gp3"
    volume_size           = 30
    delete_on_termination = true
  }

  tags = {
    Name = "kakehashi-apo-app"
  }
}

# Elastic IP for EC2 (optional but recommended for stability)
resource "aws_eip" "kakehashi_eip" {
  instance = aws_instance.kakehashi_app.id
  domain   = "vpc"

  tags = {
    Name = "kakehashi-apo-eip"
  }

  depends_on = [aws_internet_gateway.kakehashi_igw]
}

# DB Subnet Group
resource "aws_db_subnet_group" "kakehashi" {
  name       = "kakehashi-apo-subnet-group"
  subnet_ids = [aws_subnet.public.id, aws_subnet.private.id]

  tags = {
    Name = "kakehashi-apo-subnet-group"
  }
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "postgres" {
  identifier = "kakehashi-apo-db"
  engine     = "postgres"
  engine_version = "15.4"
  instance_class = var.db_instance_class
  allocated_storage = 20

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  vpc_security_group_ids = [aws_security_group.kakehashi_sg.id]
  db_subnet_group_name   = aws_db_subnet_group.kakehashi.name

  # Backup configuration
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "mon:04:00-mon:05:00"

  # Performance insights
  performance_insights_enabled = false

  # Storage encryption
  storage_encrypted = true

  skip_final_snapshot       = false
  final_snapshot_identifier = "kakehashi-apo-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  tags = {
    Name = "kakehashi-apo-postgres"
  }
}

# Data source: Ubuntu AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"]
  }

  filter {
    name   = "root-device-type"
    values = ["ebs"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Variables
variable "aws_region" {
  type        = string
  default     = "ap-northeast-1"
  description = "AWS region"
}

variable "instance_type" {
  type        = string
  default     = "t3.large"
  description = "EC2 instance type"
}

variable "db_instance_class" {
  type        = string
  default     = "db.t3.micro"
  description = "RDS instance class"
}

variable "db_name" {
  type        = string
  default     = "kakehashi_apo_poc"
  description = "Database name"
}

variable "db_username" {
  type        = string
  default     = "kakehashi"
  description = "Database username"
}

variable "db_password" {
  type        = string
  sensitive   = true
  description = "Database password - CHANGE IN PRODUCTION"
}

variable "docker_registry" {
  type        = string
  default     = ""
  description = "Docker registry URL (optional)"
}

# Outputs
output "app_public_ip" {
  value       = aws_eip.kakehashi_eip.public_ip
  description = "Public IP of the application server"
}

output "app_public_dns" {
  value       = aws_eip.kakehashi_eip.public_dns
  description = "Public DNS of the application server"
}

output "db_endpoint" {
  value       = aws_db_instance.postgres.endpoint
  description = "RDS endpoint"
  sensitive   = true
}

output "db_address" {
  value       = aws_db_instance.postgres.address
  description = "RDS address"
  sensitive   = true
}

output "security_group_id" {
  value       = aws_security_group.kakehashi_sg.id
  description = "Security group ID"
}
