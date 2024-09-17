#!/bin/bash

# Ensure the script is run with superuser privileges
if [ "$(id -u)" -ne "0" ]; then
    echo "This script must be run as root. Use 'sudo ./install_packages.sh'"
    exit 1
fi

# Detect the package manager
if command -v apt-get &> /dev/null; then
    PACKAGE_MANAGER="apt-get"
    UPDATE_CMD="apt-get update"
    INSTALL_CMD="apt-get install -y"
elif command -v dnf &> /dev/null; then
    PACKAGE_MANAGER="dnf"
    UPDATE_CMD="dnf check-update"
    INSTALL_CMD="dnf install -y"
elif command -v zypper &> /dev/null; then
    PACKAGE_MANAGER="zypper"
    UPDATE_CMD="zypper refresh"
    INSTALL_CMD="zypper install -y"
elif command -v pacman &> /dev/null; then
    PACKAGE_MANAGER="pacman"
    UPDATE_CMD="pacman -Sy"
    INSTALL_CMD="pacman -S --noconfirm"
else
    echo "Unsupported package manager. Exiting."
    exit 1
fi

# Update package list
echo "Updating package list..."
$UPDATE_CMD

# Install Python packages using system package manager
if [ "$PACKAGE_MANAGER" = "apt-get" ]; then
    $INSTALL_CMD \
        python3-pyqt5=5.15.9 \
        python3-numpy \
        python3-pyqtgraph=0.13.3 \
        python3-flask=2.3.2 \
        gunicorn \
        python3-matplotlib=3.7.2 \
        python3-plotly=5.12.0 \
        python3-pyyaml=6.0.2

elif [ "$PACKAGE_MANAGER" = "dnf" ]; then
    $INSTALL_CMD \
        python3-qt5 \
        python3-numpy \
        python3-pyqtgraph \
        python3-flask \
        gunicorn \
        python3-matplotlib \
        python3-plotly \
        python3-pyyaml

elif [ "$PACKAGE_MANAGER" = "zypper" ]; then
    $INSTALL_CMD \
        python3-qt5 \
        python3-numpy \
        python3-pyqtgraph \
        python3-flask \
        gunicorn \
        python3-matplotlib \
        python3-plotly \
        python3-pyyaml

elif [ "$PACKAGE_MANAGER" = "pacman" ]; then
    $INSTALL_CMD \
        python-pyqt5 \
        python-numpy \
        python-pyqtgraph \
        python-flask \
        gunicorn \
        python-matplotlib \
        python-plotly \
        python-yaml
fi

# Install Docker if it's not already installed
if ! command -v docker &> /dev/null; then
    echo "Docker not found, installing..."
    if [ "$PACKAGE_MANAGER" = "apt-get" ]; then
        # Install Docker for Debian-based systems
        $INSTALL_CMD \
            apt-transport-https \
            ca-certificates \
            curl \
            gnupg-agent \
            software-properties-common

        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
        add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
        $UPDATE_CMD
        $INSTALL_CMD docker-ce docker-ce-cli containerd.io

    elif [ "$PACKAGE_MANAGER" = "dnf" ]; then
        # Install Docker for RHEL-based systems
        $INSTALL_CMD \
            dnf-plugins-core \
            curl \
            device-mapper-persistent-data \
            lvm2

        curl -fsSL https://download.docker.com/linux/fedora/gpg | dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
        $INSTALL_CMD docker-ce docker-ce-cli containerd.io

    elif [ "$PACKAGE_MANAGER" = "zypper" ]; then
        # Install Docker for openSUSE
        $INSTALL_CMD \
            curl \
            libseccomp2 \
            device-mapper

        zypper ar https://download.docker.com/linux/opensuse/docker-ce.repo
        zypper ref
        $INSTALL_CMD docker-ce docker-ce-cli containerd.io

    elif [ "$PACKAGE_MANAGER" = "pacman" ]; then
        # Install Docker for Arch Linux
        $INSTALL_CMD docker
    fi
fi

echo "All packages installed successfully!"
