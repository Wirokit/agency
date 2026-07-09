#!/bin/bash

# 1. Install Certbot and its Nginx plugin via EPEL/dnf
sudo dnf install -y augeas-libs
sudo python3 -m venv /opt/certbot/
sudo /opt/certbot/bin/pip install --upgrade pip
sudo /opt/certbot/bin/pip install certbot certbot-nginx
sudo ln -s /opt/certbot/bin/certbot /usr/bin/certbot

# 2. Request and configure the SSL certificate with Nginx
# (This automatically updates your Nginx configs and handles HTTP -> HTTPS redirection)
sudo certbot --nginx \
  --non-interactive \
  --agree-tos \
  --email sami.pitkanen@wirokit.com \
  -d agency.wirokit.com