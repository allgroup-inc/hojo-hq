#!/bin/bash
set -e

# Update system packages
apt-get update
apt-get upgrade -y
apt-get install -y curl wget git

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
usermod -aG docker ubuntu

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Clone or pull the repository
cd /home/ubuntu
if [ -d "hojo-hq" ]; then
  cd hojo-hq
  git pull origin main
else
  git clone https://github.com/allgroup-inc/hojo-hq.git
  cd hojo-hq
fi

# Create .env file for docker-compose
cat > .env << EOF
DB_USER=${db_user}
DB_PASSWORD=${db_password}
DB_NAME=${db_name}
DATABASE_URL=postgresql://${db_user}:${db_password}@db:5432/${db_name}
NODE_ENV=production
PORT=3000
ENTRA_CLIENT_ID=${ENTRA_CLIENT_ID:-}
ENTRA_CLIENT_SECRET=${ENTRA_CLIENT_SECRET:-}
ENTRA_CALLBACK_URL=http://${db_host}:3000/auth/callback
EOF

# Set proper ownership
chown -R ubuntu:ubuntu /home/ubuntu/hojo-hq

# Start Docker containers
cd /home/ubuntu/hojo-hq
docker-compose build
docker-compose up -d

# Log successful startup
echo "KAKEHASHI APO PoC deployment completed successfully at $(date)" | tee /var/log/kakehashi-deployment.log
