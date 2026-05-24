# WireGuard VPN Server Autoinstaller & Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a secure, lightweight, self-contained Bash script to install, configure, and manage a WireGuard VPN server on Debian/Ubuntu systems, verified by static analysis tests in pytest.

**Architecture:** A robust Bash script containing modular functions for bootstrapping, configuration, and interactive peer management. It stores client configuration profiles under `/etc/wireguard/clients/<name>/` and uses graceful reloads (`wg syncconf`) to avoid disruption.

**Tech Stack:** Bash, WireGuard, `iptables`, `qrencode`, Python 3.10+ (for pytest syntax verification).

---

### Task 1: Initialize Syntax and Static Analysis Tests

**Files:**
- Create: `school-mail-bot/tests/test_wireguard_install.py`
- Create: `wireguard-install.sh` (Minimal shell skeleton)

- [ ] **Step 1: Create a minimal skeleton for the installer script**

Create `wireguard-install.sh` with the basic bash header:
```bash
#!/usr/bin/env bash
set -euo pipefail

# WireGuard Autoinstaller & Manager
echo "WireGuard Installer"
```

- [ ] **Step 2: Create a syntax validation test in pytest**

Create `school-mail-bot/tests/test_wireguard_install.py` to run syntax validation (`bash -n`) on our script:
```python
import subprocess
from pathlib import Path

def test_script_syntax_is_valid() -> None:
    """Verifies that the bash script contains no syntax errors."""
    script_path = Path(__file__).parents[2] / "wireguard-install.sh"
    assert script_path.exists(), "Script file does not exist"
    
    # Run bash syntax check: bash -n <script>
    result = subprocess.run(
        ["bash", "-n", str(script_path)],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Bash syntax check failed:\n{result.stderr}"
```

- [ ] **Step 3: Run the test to verify it passes**

Run: `pytest school-mail-bot/tests/test_wireguard_install.py`
Expected: PASS

- [ ] **Step 4: Commit the initial files**

```bash
git add wireguard-install.sh school-mail-bot/tests/test_wireguard_install.py
git commit -m "test: add bash syntax check for WireGuard script skeleton"
```

---

### Task 2: Implement OS Checks, Bootstrapping, and Package Installation

**Files:**
- Modify: `wireguard-install.sh`

- [ ] **Step 1: Implement root checks, OS detection, and package installation logic**

Edit `wireguard-install.sh` to include pre-flight OS check and the installer routine:
```bash
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
```

- [ ] **Step 2: Run pytest to ensure syntax remains perfectly valid**

Run: `pytest school-mail-bot/tests/test_wireguard_install.py`
Expected: PASS

- [ ] **Step 3: Commit bootstrapping changes**

```bash
git add wireguard-install.sh
git commit -m "feat: add root check, OS detection, and dependencies logic"
```

---

### Task 3: Implement IP Forwarding, Local Firewall Setup, and Server Key Generation

**Files:**
- Modify: `wireguard-install.sh`

- [ ] **Step 1: Implement IP forwarding, key generation, and firewall management**

Add the following functions to `wireguard-install.sh`:
```bash
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
```

- [ ] **Step 2: Run pytest to verify syntax correctness**

Run: `pytest school-mail-bot/tests/test_wireguard_install.py`
Expected: PASS

- [ ] **Step 3: Commit changes**

```bash
git add wireguard-install.sh
git commit -m "feat: add IP forwarding, host firewall config, and server keygen"
```

---

### Task 4: Implement Main WireGuard Configuration (`wg0.conf`) Generation & Server Start

**Files:**
- Modify: `wireguard-install.sh`

- [ ] **Step 1: Implement dynamic interface resolution and `wg0.conf` generation**

Add `setup_server_config` and systemd initialization functions:
```bash
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
```

- [ ] **Step 2: Run pytest to ensure syntax validation passes**

Run: `pytest school-mail-bot/tests/test_wireguard_install.py`
Expected: PASS

- [ ] **Step 3: Commit changes**

```bash
git add wireguard-install.sh
git commit -m "feat: implement primary interface detection, server wg0.conf, and startup"
```

---

### Task 5: Implement Interactive Client Addition, Key Gen, and QR Rendering

**Files:**
- Modify: `wireguard-install.sh`

- [ ] **Step 1: Implement client IP calculation, peer blocks, config file generation, and QR display**

Add client creation and live config reloading functions:
```bash
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
```

- [ ] **Step 2: Run pytest syntax checks**

Run: `pytest school-mail-bot/tests/test_wireguard_install.py`
Expected: PASS

- [ ] **Step 3: Commit changes**

```bash
git add wireguard-install.sh
git commit -m "feat: implement interactive client addition with syncconf and QR code"
```

---

### Task 6: Implement Client Revocation, Client Listing, and Interactive Command Menu

**Files:**
- Modify: `wireguard-install.sh`

- [ ] **Step 1: Implement list and revoke logic along with an interactive menu CLI**

Add the list, revoke, and main interface loop functions:
```bash
# List all active clients
list_clients() {
    if [[ ! -d "${CLIENTS_DIR}" ]] || [[ -z "$(ls -A "${CLIENTS_DIR}")" ]]; then
        echo "No clients configured."
        return 0
    fi
    
    echo -e "\n--- Configured WireGuard Clients ---"
    printf "%-20s %-15s %-30s\n" "Name" "IP Address" "Created"
    echo "--------------------------------------------------------"
    for dir in "${CLIENTS_DIR}"/*; do
        if [[ -d "${dir}" ]]; then
            local name
            name=$(basename "${dir}")
            local client_ip=""
            if [[ -f "${dir}/wg0-client.conf" ]]; then
                client_ip=$(grep "Address" "${dir}/wg0-client.conf" | awk '{print $3}' | cut -d'/' -f1)
            fi
            local created
            created=$(date -r "${dir}" "+%Y-%m-%d %H:%M:%S")
            printf "%-20s %-15s %-30s\n" "${name}" "${client_ip}" "${created}"
        fi
    done
    echo ""
}

# Revoke (delete) client
revoke_client() {
    list_clients
    if [[ ! -d "${CLIENTS_DIR}" ]] || [[ -z "$(ls -A "${CLIENTS_DIR}")" ]]; then
        return 0
    fi
    
    local name
    read -rp "Enter the name of the client to revoke: " name
    
    if [[ -z "${name}" ]] || [[ ! -d "${CLIENTS_DIR}/${name}" ]]; then
        echo "Error: Client '${name}' does not exist." >&2
        return 1
    fi
    
    local client_pub
    client_pub=$(cat "${CLIENTS_DIR}/${name}/public.key")
    
    echo "Removing client '${name}'..."
    
    # Create a temporary config without the revoked peer blocks
    local temp_conf
    temp_conf=$(mktemp)
    
    # Filter out peer block of client from wg0.conf
    # We remove the [Peer] block matching the PublicKey of the revoked client
    # Utilizing an elegant awk state machine to discard the matching peer block
    awk -v pubkey="${client_pub}" '
    BEGIN { inside_peer = 0; peer_text = "" }
    /^\[Peer\]/ {
        if (inside_peer) {
            if (peer_text !~ pubkey) {
                print peer_text
            }
            peer_text = ""
        }
        inside_peer = 1
        peer_text = $0 "\n"
        next
    }
    inside_peer {
        peer_text = peer_text $0 "\n"
        if (NF == 0 || $0 ~ /^\[Interface\]/) {
            inside_peer = 0
            if (peer_text !~ pubkey) {
                print peer_text
            }
            peer_text = ""
        }
        next
    }
    { print }
    END {
        if (inside_peer && peer_text !~ pubkey) {
            print peer_text
        }
    }
    ' "${WG_DIR}/wg0.conf" > "${temp_conf}"
    
    mv "${temp_conf}" "${WG_DIR}/wg0.conf"
    chmod 600 "${WG_DIR}/wg0.conf"
    
    # Gracefully sync WireGuard rules
    wg syncconf wg0 <(wg-quick strip wg0)
    
    # Delete client folder
    rm -rf "${CLIENTS_DIR}/${name}"
    echo "Client '${name}' revoked and files deleted successfully."
}

# Initial interactive installation wizard
install_wizard() {
    check_root
    check_os
    
    if [[ -f "${WG_DIR}/wg0.conf" ]]; then
        echo "WireGuard is already installed."
        return 0
    fi
    
    echo "Welcome to the WireGuard Autoinstaller!"
    local port
    read -rp "Enter the UDP port to listen on [Default: 51820]: " port
    port="${port:-51820}"
    
    install_dependencies
    enable_ip_forwarding
    configure_host_firewall "${port}"
    generate_server_keys
    setup_server_config "${port}"
    start_wireguard
    
    mkdir -p "${CLIENTS_DIR}"
    chmod 700 "${CLIENTS_DIR}"
    echo "Installation completed successfully."
}

# Main script menu
main_menu() {
    while true; do
        echo "=============================="
        echo " WireGuard Server Manager"
        echo "=============================="
        echo "1. Add New Client"
        echo "2. List Clients"
        echo "3. Revoke/Delete Client"
        echo "4. Install WireGuard (Initial)"
        echo "5. Exit"
        echo "=============================="
        local choice
        read -rp "Enter choice [1-5]: " choice
        
        case "${choice}" in
            1) check_root; add_client ;;
            2) check_root; list_clients ;;
            3) check_root; revoke_client ;;
            4) install_wizard ;;
            5) exit 0 ;;
            *) echo "Invalid option." ;;
        esac
        echo ""
    done
}

# Check if script is executed or sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ ! -f "${WG_DIR}/wg0.conf" ]]; then
        install_wizard
    fi
    main_menu
fi
```

- [ ] **Step 2: Run pytest to guarantee flawless bash syntax check**

Run: `pytest school-mail-bot/tests/test_wireguard_install.py`
Expected: PASS

- [ ] **Step 3: Commit completed script and tests**

```bash
git add wireguard-install.sh
git commit -m "feat: complete WireGuard installation script with full client management"
```
