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

# Enable IPv4 Forwarding
enable_ip_forwarding() {
    echo "Enabling IPv4 forwarding..."
    if grep -q "^#net.ipv4.ip_forward=1" /etc/sysctl.conf; then
        sed -i 's/^#net.ipv4.ip_forward=1/net.ipv4.ip_forward=1/' /etc/sysctl.conf
    elif grep -q "^net.ipv4.ip_forward=1" /etc/sysctl.conf; then
        : # Already enabled
    else
        echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
    fi
    sysctl -p
}

# Open host local firewall ports
configure_host_firewall() {
    local port="$1"
    if command -v ufw >/dev/null; then
        if ufw status | grep -q "Status: active"; then
            echo "UFW is active. Allowing UDP port ${port}..."
            ufw allow "${port}/udp"
        fi
    fi
    # Add to iptables INPUT rules if ufw not managing
    if command -v iptables >/dev/null; then
        if ! iptables -C INPUT -p udp --dport "${port}" -j ACCEPT 2>/dev/null; then
            echo "Adding iptables rule to accept incoming UDP traffic on port ${port}..."
            iptables -A INPUT -p udp --dport "${port}" -j ACCEPT
        fi
    fi
}

# Generate Server Private/Public Keypair
generate_server_keys() {
    mkdir -p "${WG_DIR}"
    chmod 700 "${WG_DIR}"
    
    if [[ ! -f "${WG_DIR}/private.key" ]]; then
        echo "Generating server keys..."
        wg genkey | tee "${WG_DIR}/private.key" | wg pubkey > "${WG_DIR}/public.key"
        chmod 600 "${WG_DIR}/private.key" "${WG_DIR}/public.key"
    fi
}
