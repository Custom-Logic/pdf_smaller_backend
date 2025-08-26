#!/bin/bash

# Update system
apt-get update
apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create application directory
mkdir -p /opt/pdf-compression-server
cd /opt/pdf-compression-server

# Copy application files (you would typically clone a Git repository here)
# git clone <your-repository> .

# Build and start containers
docker-compose up -d --build

# Set up Nginx (if not using Docker for reverse proxy)
apt-get install -y nginx
cp nginx.conf /etc/nginx/sites-available/pdf-compression
ln -s /etc/nginx/sites-available/pdf-compression /etc/nginx/sites-enabled/
systemctl restart nginx

# Set up firewall
ufw allow 80
ufw allow 22
ufw enable

echo "PDF Compression Server setup complete!"
