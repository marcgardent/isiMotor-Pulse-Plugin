# 🌐 isiMotor UDP Network Architecture & Routing Guide

This guide explains how to route and optimize **isiMotor-RawUDP-Plugin** telemetry streams across different network topologies: **Local Loopback**, **LAN Unicast**, **Multicast**, **Wi-Fi networks**, and **Public IP / Internet (Remote Pit-Wall / Telemetry Engineers)**.

---

## 📑 Table of Contents

1. [Network Modes Overview (Unicast vs Multicast vs Broadcast)](#1-network-modes-overview)
2. [Mode 1: Unicast (1-to-1) — *Recommended for Wi-Fi*](#2-mode-1-unicast-1-to-1)
3. [Mode 2: Multicast (1-to-N) — *Subscribed Multi-Client*](#3-mode-2-multicast-1-to-n)
4. [Mode 3: Broadcast (1-to-All) — *LAN Only*](#4-mode-3-broadcast-1-to-all)
5. [Managing Telemetry on Wi-Fi Networks](#5-managing-telemetry-on-wi-fi-networks)
6. [Streaming Over Public IP / Internet / 4G (Remote Telemetry)](#6-streaming-over-public-ip--internet--4g)
7. [Firewall & Troubleshooting Checklist](#7-firewall--troubleshooting-checklist)

---

## 1. Network Modes Overview

| Feature | **Unicast (1:1)** | **Multicast (1:N)** | **Broadcast (1:All)** |
|---|---|---|---|
| **Destination IP** | `127.0.0.1` or `192.168.1.X` | `239.255.0.1` (Class D) | `255.255.255.255` or `192.168.1.255` |
| **Recipients** | Exactly 1 device | All subscribed devices (IGMP) | Every device on the subnet |
| **Wi-Fi Performance** | ⚡ **Optimal** (Hardware ACKs, MIMO, 100+ Mbps) | ⚠️ **Medium** (Requires IGMP Snooping) | ❌ **Poor** (Basic beacon rate 1-6 Mbps, packet drops) |
| **Network Overhead** | Low (direct point-to-point) | Low (switches duplicate only to listeners) | High (wakes all devices on LAN) |
| **Public WAN / Internet** | ✅ Yes (Direct IP, Port Forward, or VPN) | ❌ Blocked by ISP routers | ❌ Blocked by ISP routers |
| **Multi-App Support** | Single listener per IP | Infinite listeners simultaneously | Infinite listeners simultaneously |

---

## 2. Mode 1: Unicast (1-to-1)

Unicast sends UDP datagrams directly from the game PC to a single destination IP address.

### Configuration (`isiMotor_RawUDP.ini`)

```ini
[Network]
; Scenario A: Same PC (SimPad, Sniffer, Local App)
TargetIP=127.0.0.1
TargetPort=5000

; Scenario B: Dedicated Tablet / Smartphone / Secondary Rig PC on LAN
; TargetIP=192.168.1.42
; TargetPort=5000
```

### Why Unicast is the Gold Standard for Wi-Fi

* **Wi-Fi 802.11 Unicast Frames**: Wi-Fi access points communicate with unicast destinations using **hardware link-layer Acknowledgements (ACKs)**, dynamic beamforming, and maximum negotiated PHY rates (hundreds of Mbps).
* If a packet suffers radio interference, the Wi-Fi card immediately retransmits it at the MAC layer within microseconds.
* Unicast does not saturate the wireless medium.

### Python Receiver Code (Unicast)

```python
import socket
from isimotor_rawudp_client.decoder import decode_packet

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", 5000)) # Bind to all interfaces to receive local or LAN unicast

while True:
    data, addr = sock.recvfrom(65535)
    packet = decode_packet(data)
    if packet:
        print(f"Received {type(packet).__name__} from {addr}")
```

---

## 3. Mode 2: Multicast (1-to-N)

Multicast allows the game plugin to send a **single UDP packet** that is automatically replicated by network switches only to devices and applications that have explicitly subscribed to the multicast group.

### IP Range & Recommended Multicast Group

IPv4 Multicast addresses range from `224.0.0.0` to `239.255.255.255`.
For local private networks (RFC 2365), use the **Administratively Scoped IPv4 Multicast range**:
* Recommended IP: `239.255.0.1`

### Configuration (`isiMotor_RawUDP.ini`)

```ini
[Network]
TargetIP=239.255.0.1
TargetPort=5000
```

### Python Receiver Code (Multicast Group Subscription)

To receive multicast packets, client applications must join the multicast group via IGMP (`IP_ADD_MEMBERSHIP`):

```python
import socket
import struct
from isimotor_rawudp_client.decoder import decode_packet

MULTICAST_GROUP = "239.255.0.1"
PORT = 5000

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# On Linux/macOS, SO_REUSEPORT allows multiple independent processes to bind the same port:
if hasattr(socket, "SO_REUSEPORT"):
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except Exception:
        pass

# Bind to the multicast port
sock.bind(("", PORT))

# Tell the OS kernel to join the multicast group on all network interfaces
mreq = struct.pack("4sl", socket.inet_aton(MULTICAST_GROUP), socket.INADDR_ANY)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

print(f"Subscribed to Multicast group {MULTICAST_GROUP}:{PORT}...")
while True:
    data, addr = sock.recvfrom(65535)
    packet = decode_packet(data)
    if packet:
        print(f"Decoded {type(packet).__name__}")
```

---

## 4. Mode 3: Broadcast (1-to-All)

Broadcast sends packets to every device connected to the subnet (`255.255.255.255` or `192.168.1.255`).

```ini
[Network]
TargetIP=255.255.255.255
TargetPort=5000
```

> **Warning:**
> **Avoid Broadcast on Wi-Fi networks at 100 Hz!**
> Wi-Fi routers transmit broadcast frames at the lowest basic legacy rate (1 Mbps to 6 Mbps) without link-layer ACKs to ensure all legacy devices can hear it. Sending 100 packets/sec (~1.5 Mbps) over broadcast will saturate the Wi-Fi airtime, causing high latency, packet loss, and stutter on all devices on your Wi-Fi network.

---

## 5. Managing Telemetry on Wi-Fi Networks

When streaming high-frequency 100 Hz telemetry to a wireless device (e.g. iPad, Android tablet, laptop):

```
┌─────────────────┐       Ethernet       ┌───────────────┐        802.11ac/ax       ┌─────────────────┐
│   Sim Gaming    │ ───────────────────> │  Wi-Fi Router │ ‧ ‧ ‧ ‧ ‧ ‧ ‧ ‧ ‧ ‧ ‧ ‧> │ Wireless Tablet │
│  PC (Plugin)    │                      │  / AP Switch  │     (Unicast 100Hz)      │ (Dashboard UI)  │
└─────────────────┘                      └───────────────┘                          └─────────────────┘
```

### Best Practices for Wi-Fi:

1. **Use Unicast over Wi-Fi**:
   * Set `TargetIP=192.168.1.XX` (the specific IP of the tablet).
   * Assign a **DHCP Static Reservation** in your router for your tablet so its IP never changes.
2. **If using Multicast on Wi-Fi**:
   * Access your Wi-Fi router admin page and enable **IGMP Snooping**.
   * Enable **Multicast Enhancement / Multicast-to-Unicast (M2U)**: This setting instructs the Wi-Fi router to convert multicast packets into high-speed unicast frames over the wireless link.
3. **Use 5 GHz or 6 GHz Wi-Fi (Wi-Fi 5/6/6E/7)**:
   * Avoid congested 2.4 GHz bands which suffer from Bluetooth / microwave interference.

---

## 6. Streaming Over Public IP / Internet / 4G

Telemetry multicast and broadcast **cannot cross the Internet** (they are dropped at the ISP gateway). To stream telemetry to a remote engineer, coach, pit-wall, or streamer in another city, use one of the following methods:

### Method A: VPN Mesh (Tailscale / ZeroTier / WireGuard) — ⭐ *RECOMMENDED*

A mesh VPN creates a secure, encrypted peer-to-peer virtual local network between devices anywhere in the world without opening ports on your router.

```
┌───────────────────────┐                                 ┌───────────────────────┐
│   Sim Racer PC        │                                 │ Remote Race Engineer  │
│   (Plugin)            │                                 │ (Pit-Wall Dashboard)  │
│   Tailscale IP:       │   Encrypted WireGuard Tunnel    │ Tailscale IP:         │
│   100.64.1.10         │ ══════════════════════════════> │ 100.64.1.25           │
└───────────────────────┘                                 └───────────────────────┘
```

1. Install [Tailscale](https://tailscale.com/) or [ZeroTier](https://zerotier.com/) on both the gaming PC and the remote device.
2. Note the virtual IP of the receiver (e.g., `100.64.1.25`).
3. Set in `isiMotor_RawUDP.ini`:
   ```ini
   [Network]
   TargetIP=100.64.1.25
   TargetPort=5000
   ```
4. **Advantages**:
   * Zero router configuration (traverses 4G/5G, CGNAT, hotel Wi-Fi, Starlink).
   * Fully encrypted end-to-end.
   * Secure: nobody else on the internet can probe or flood your socket.

---

### Method B: Direct Public IP & Port Forwarding (NAT)

If a VPN is not an option, you can stream directly over public IPv4 using router port forwarding:

```
┌──────────────────────┐       Internet        ┌──────────────────────┐    Port Forward     ┌──────────────────────┐
│  Sim Racer PC        │ ────────────────────> │ Remote Router Box    │ ──────────────────> │ Remote Engineer PC   │
│  TargetIP=82.64.x.y  │     (Public WAN)      │ Public IP: 82.64.x.y │    UDP Port 5000    │ LAN: 192.168.1.50    │
└──────────────────────┘                       └──────────────────────┘                     └──────────────────────┘
```

1. **On the Receiver's Internet Router**:
   * Open the router administration dashboard.
   * Add a **Port Forwarding (NAT)** rule:
     * Protocol: `UDP`
     * External Port: `5000`
     * Internal IP: `192.168.1.50` (Local IP of the engineer's PC)
     * Internal Port: `5000`
2. **Find the Receiver's Public IP**:
   * On the receiver PC, visit `https://ifconfig.me` or `curl ifconfig.me`.
3. **On the Sender (Game PC)**:
   * Configure `isiMotor_RawUDP.ini`:
     ```ini
     [Network]
     TargetIP=82.64.x.y  ; Receiver's Public IP
     TargetPort=5000
     ```

> **Caution:**
> Direct UDP port forwarding exposes that port to the open internet. Anyone knowing the public IP could send malicious packets to the receiver application. For secure long-term remote team telemetry, **Method A (Tailscale/VPN)** is strongly advised.

---

### Method C: Cloud UDP Relay / WebSocket Proxy

For multi-viewer web dashboards or race broadcast overlays:

```
┌─────────────┐   Raw UDP (100Hz)    ┌───────────────────────────┐   WebSockets / HTTP   ┌───────────────────┐
│ Sim Game PC │ ───────────────────> │ Cloud VPS (Relay Server)  │ ────────────────────> │ 100+ Web Viewers  │
└─────────────┘                      │ Python / Go WebSocket Hub │                       │ Browser Overlays  │
                                     └───────────────────────────┘                       └───────────────────┘
```

* The game sends unicast UDP to a Linux VPS (e.g. AWS, Hetzner, DigitalOcean).
* A lightweight server (written in Python/FastAPI or Go) parses the packets using `isimotor-rawudp-client` and broadcasts JSON / compact frames over WebSockets to multiple web viewers simultaneously.

---

## 7. Firewall & Troubleshooting Checklist

### Windows Firewall Configuration (Receiver PC)
If the receiver PC is not getting any packets:

1. Open PowerShell as Administrator on the receiver PC:
   ```powershell
   New-NetFirewallRule -DisplayName "isiMotor Raw UDP Inbound (5000)" -Direction Inbound -LocalPort 5000 -Protocol UDP -Action Allow
   ```

### Linux Firewall Configuration
On Linux host machines:
```bash
sudo ufw allow 5000/udp
```

### Quick Diagnostic Commands

* **Verify active UDP listener on port 5000**:
  * Windows: `netstat -ano | findstr :5000`
  * Linux: `ss -ulnp | grep 5000`
* **Sniff incoming raw UDP packets live**:
  * Using our interactive TUI:
    ```bash
    python benchmark/sniffer.py --port 5000
    ```
  * Using `tcpdump` (Linux):
    ```bash
    sudo tcpdump -i any -n udp port 5000 -X
    ```
