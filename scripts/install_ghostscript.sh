#!/bin/bash

# Install Ghostscript based on OS
if [ -f /etc/debian_version ]; then
    # Debian/Ubuntu
    apt-get update
    apt-get install -y ghostscript
elif [ -f /etc/redhat-release ]; then
    # CentOS/RHEL
    yum install -y ghostscript
elif [ -f /etc/arch-release ]; then
    # Arch Linux
    pacman -S ghostscript
else
    echo "Unsupported OS for automatic Ghostscript installation"
    exit 1
fi

# Verify installation
gs --version
