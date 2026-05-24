# Design Spec: WireGuard VPN Server Autoinstaller & Manager

## Overview
A secure, lightweight, and highly optimized self-contained Bash script to install, configure, and manage a WireGuard VPN server on an Oracle Cloud Free Tier instance running Debian or Ubuntu. It operates with a minimal RAM footprint (<20MB) to ensure coexistence with background Python scripts.

## System Bootstrapping & OS Integration

### Pre-flight Checks
- Must be executed with root/sudo privileges.
- Operating System verification (`Debian` or `Ubuntu`) by sourcing `/etc/os-release`.

### Packages Installed
- `wireguard` (Core VPN engine & utilities)
- `iptables` / `iptables-persistent` (IP routing and NAT rules)
- `qrencode` (Rendering connection QR codes in the terminal)

### Kernel Parameter Customization
- Automatically sets/uncomments `net.ipv4.ip_forward=1` inside `/etc/sysctl.conf`.
- Executes `sysctl -p` to apply IP forwarding immediately without requiring a reboot.

### Local Host Firewall Automation
- Checks for active local firewall rules:
  - If `ufw` is active, inserts a rule to allow incoming UDP traffic on the specified WireGuard port.
  - If `iptables` is used directly, inserts the rule into the INPUT chain.

---

## Server Configuration & NAT Interface

### Key Generation
- Server private key generated to `/etc/wireguard/server_private.key` (chmod 600).
- Server public key derived and saved to `/etc/wireguard/server_public.key` (chmod 600).

### Public Interface & IP Discovery
- Dynamically resolves public IP address of the server via external secure curl queries (`https://api.ipify.org` or `https://icanhazip.com`).
- Dynamically resolves primary active network interface using `ip route show default | awk '{print $5}'` (typically `eth0` or `ens3` on Oracle Cloud VMs).

### Core Server Interface (`/etc/wireguard/wg0.conf`)
- Address: `10.8.0.1/24`
- Listening Port: Configurable (default `51820`).
- NAT routing directives via `PostUp` and `PostDown`:
  - `PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o <PRIMARY_INTERFACE> -j MASQUERADE; iptables -A FORWARD -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT`
  - `PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o <PRIMARY_INTERFACE> -j MASQUERADE; iptables -D FORWARD -o wg0 -m state --state RELATED,ESTABLISHED -j ACCEPT`

### Service Control
- Enables and starts `wg-quick@wg0` via `systemctl`.

---

## Interactive Client (Peer) Management & Storage

### Dedicated Client Storage Directory
- Created at `/etc/wireguard/clients/` with strict directory permission `0700`.
- Each client/peer configuration files are saved inside `/etc/wireguard/clients/<client_name>/` (chmod 700 for directories, 600 for files):
  - `private.key`: Client private key.
  - `public.key`: Client public key.
  - `preshared.key`: Pre-shared key for quantum-resistant symmetric security.
  - `wg0-client.conf`: Generated client config profile.

### Operations

#### 1. Add New Client
- Validates user input to ensure alphanumeric characters only.
- Calculates next available IP within the `10.8.0.0/24` subnet:
  - Scans existing files or parses `wg0.conf` to check current IPs.
  - Default starting host is `10.8.0.2`.
- Generates client private/public keypair and pre-shared key.
- Appends `[Peer]` configuration block to `/etc/wireguard/wg0.conf`:
  ```ini
  [Peer]
  PublicKey = <CLIENT_PUBLIC_KEY>
  PresharedKey = <CLIENT_PRESHARED_KEY>
  AllowedIPs = <CLIENT_IP>/32
  ```
- Gracefully reloads WireGuard live without dropping active client connections:
  ```bash
  wg syncconf wg0 <(wg-quick strip wg0)
  ```
- Creates a customized client profile at `/etc/wireguard/clients/<client_name>/wg0-client.conf`:
  ```ini
  [Interface]
  PrivateKey = <CLIENT_PRIVATE_KEY>
  Address = <CLIENT_IP>/24
  DNS = 9.9.9.9
  
  [Peer]
  PublicKey = <SERVER_PUBLIC_KEY>
  PresharedKey = <CLIENT_PRESHARED_KEY>
  Endpoint = <SERVER_PUBLIC_IP>:<WG_PORT>
  AllowedIPs = 0.0.0.0/0
  PersistentKeepalive = 25
  ```
- Generates and outputs a QR code to the console from `wg0-client.conf` via `qrencode -t ansiutf8`.

#### 2. List Clients
- Scans and lists folders inside `/etc/wireguard/clients/`.
- Prints the client name, assigned IP address, and date created.

#### 3. Revoke/Delete Client
- Prompts user to choose from a list of current clients.
- Removes the specific `[Peer]` block from `/etc/wireguard/wg0.conf`.
- Gracefully updates current wireguard setup with `wg syncconf wg0 <(wg-quick strip wg0)`.
- Deletes the client's dedicated subdirectory from `/etc/wireguard/clients/`.

---

## Security & Performance Verification
- Client DNS defaults to Quad9 (`9.9.9.9`) to prevent DNS leaks.
- Keeps connections alive with `PersistentKeepalive = 25` to prevent Oracle's stateful firewalls from terminating idle connections.
- Permissions on private keys and configuration files must always be set to `0600`.
