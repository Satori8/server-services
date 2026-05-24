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

# Detect primary network interface
get_primary_interface() {
    ip route show default | awk '{print $5}' | head -n1
}

# Create server wg0.conf
setup_server_config() {
    local port="${1:-51820}"
    local interface
    interface=$(get_primary_interface)
    
    if [[ -z "${interface}" ]]; then
        echo "Error: Could not automatically detect primary network interface." >&2
        exit 1
    fi
    
    local server_priv
    server_priv=$(cat "${WG_DIR}/private.key")
    
    echo "Creating ${WG_DIR}/wg0.conf..."
    cat <<EOF > "${WG_DIR}/wg0.conf"
[Interface]
Address = 10.8.0.1/24
SaveConfig = false
ListenPort = ${port}
PrivateKey = ${server_priv}

# NAT Routing Rules
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o ${interface} -j MASQUERADE; iptables -A FORWARD -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o ${interface} -j MASQUERADE; iptables -D FORWARD -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT
EOF
    chmod 600 "${WG_DIR}/wg0.conf"
}

# Start WireGuard service
start_wireguard() {
    echo "Starting WireGuard service..."
    systemctl enable wg-quick@wg0
    systemctl start wg-quick@wg0
}

# Fetch external public IP of VPS
get_public_ip() {
    curl -s --max-time 10 https://api.ipify.org || curl -s --max-time 10 https://icanhazip.com || echo "YOUR_SERVER_PUBLIC_IP"
}

# Generate next available IP in 10.8.0.0/24 subnet
get_next_client_ip() {
    local base_ip="10.8.0."
    local last_octet=2
    while [[ ${last_octet} -le 254 ]]; do
        local candidate="${base_ip}${last_octet}"
        # Check if the candidate IP is already written to wg0.conf or folders
        if ! grep -q "${candidate}" "${WG_DIR}/wg0.conf" 2>/dev/null && [[ ! -d "${CLIENTS_DIR}/${candidate}" ]]; then
            echo "${candidate}"
            return 0
        fi
        ((last_octet++))
    done
    echo "Error: No available IPs in the VPN subnet." >&2
    exit 1
}

# Add client peer
add_client() {
    local name
    read -rp "Enter unique client name (alphanumeric only): " name
    # Sanitize name
    name=$(echo "${name}" | tr -dc 'a-zA-Z0-9_')
    
    if [[ -z "${name}" ]]; then
        echo "Error: Invalid client name." >&2
        return 1
    fi
    
    if [[ -d "${CLIENTS_DIR}/${name}" ]]; then
        echo "Error: Client '${name}' already exists." >&2
        return 1
    fi
    
    local client_ip
    client_ip=$(get_next_client_ip)
    
    echo "Creating client config for ${name} (IP: ${client_ip})..."
    
    local client_dir="${CLIENTS_DIR}/${name}"
    mkdir -p "${client_dir}"
    chmod 700 "${client_dir}"
    
    # Generate client keys
    local cli_priv cli_pub cli_psk
    cli_priv=$(wg genkey)
    cli_pub=$(echo "${cli_priv}" | wg pubkey)
    cli_psk=$(wg genpsk)
    
    echo "${cli_priv}" > "${client_dir}/private.key"
    echo "${cli_pub}" > "${client_dir}/public.key"
    echo "${cli_psk}" > "${client_dir}/preshared.key"
    chmod 600 "${client_dir}/private.key" "${client_dir}/public.key" "${client_dir}/preshared.key"
    
    local server_pub
    server_pub=$(cat "${WG_DIR}/public.key")
    local public_ip
    public_ip=$(get_public_ip)
    local server_port
    server_port=$(grep "ListenPort" "${WG_DIR}/wg0.conf" | awk '{print $3}')
    
    # Append Peer block to server wg0.conf
    cat <<EOF >> "${WG_DIR}/wg0.conf"

[Peer]
# Name = ${name}
PublicKey = ${cli_pub}
PresharedKey = ${cli_psk}
AllowedIPs = ${client_ip}/32
EOF
    
    # Live reload WireGuard gracefully without dropping connections
    wg syncconf wg0 <(wg-quick strip wg0)
    
    # Create client configuration file
    cat <<EOF > "${client_dir}/wg0-client.conf"
[Interface]
PrivateKey = ${cli_priv}
Address = ${client_ip}/24
DNS = ${DEFAULT_DNS}

[Peer]
PublicKey = ${server_pub}
PresharedKey = ${cli_psk}
Endpoint = ${public_ip}:${server_port}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF
    chmod 600 "${client_dir}/wg0-client.conf"
    
    echo -e "\n--- Client Configuration File (/etc/wireguard/clients/${name}/wg0-client.conf) ---"
    cat "${client_dir}/wg0-client.conf"
    echo -e "--------------------------------------------------------------------------------\n"
    
    if command -v qrencode >/dev/null; then
        echo "Scan the QR code below to connect on mobile devices:"
        qrencode -t ansiutf8 < "${client_dir}/wg0-client.conf"
    fi
}
