#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# CONSTANTS & CONFIGURATION
# -----------------------------------------------------------------------------
WG_DIR="/etc/wireguard"
CLIENTS_DIR="${WG_DIR}/clients"
DEFAULT_PORT="51820"
DEFAULT_SUBNET="10.8.0.0/24"
DEFAULT_DNS="9.9.9.9"

# Ensure script is run as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        echo "Error: This script must be run as root (sudo)." >&2
        exit 1
    fi
}

# Verify OS compatibility (Debian/Ubuntu)
check_os() {
    if [[ -f /etc/os-release ]]; then
        # Sourcing /etc/os-release to identify distribution ID
        # shellcheck disable=SC1091
        . /etc/os-release
        if [[ "${ID}" != "ubuntu" && "${ID}" != "debian" ]]; then
            echo "Error: This script only supports Debian or Ubuntu." >&2
            exit 1
        fi
    else
        echo "Error: Sourcing /etc/os-release failed. Unsupported OS." >&2
        exit 1
    fi
}

# Install dependencies
install_dependencies() {
    echo "Updating packages and installing WireGuard..."
    apt-get update -y
    apt-get install -y wireguard iptables qrencode
}
