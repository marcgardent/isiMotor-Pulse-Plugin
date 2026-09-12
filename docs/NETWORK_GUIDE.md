# 🌐 isiMotor ZeroMQ Network Architecture & Routing Guide

This guide explains how to route **isiMotor-RawUDP-Plugin** telemetry streams across different network topologies using its **ZeroMQ PUB/SUB transport over TCP**: **Local Loopback**, **LAN**, **Multiple Simultaneous Consumers**, and **Public IP / Internet (Remote Pit-Wall / Telemetry Engineers)**.

---

## 📑 Table of Contents

1. [How the Transport Works (PUB/SUB, Bind vs Connect)](#1-how-the-transport-works)
2. [Local Loopback (Same PC)](#2-local-loopback-same-pc)
3. [LAN — Wi-Fi Tablet or Dashboard Device](#3-lan--wi-fi-tablet-or-dashboard-device)
4. [Multiple Simultaneous Consumers](#4-multiple-simultaneous-consumers)
5. [Streaming Over Public IP / Internet / 4G (Remote Telemetry)](#5-streaming-over-public-ip--internet--4g)
6. [Firewall & Troubleshooting Checklist](#6-firewall--troubleshooting-checklist)

---

## 1. How the Transport Works

The plugin uses **ZeroMQ PUB/SUB, on TCP only** (no UDP, no multicast/broadcast transport). Two independent socket pairs are involved:

| Channel | Plugin role | Client role | Config keys | Default port |
|---|---|---|---|---|
| **Outbound telemetry** | **PUB**, binds | **SUB**, connects | `TcpHost` / `TcpPort` | `5000` |
| **Inbound commands** (hardware controls, weather overrides) | **SUB**, binds | **PUB**, connects | `InboundTcpHost` / `InboundTcpPort` | `5001` |

The plugin is always the side that **binds** (it is the long-lived process for the duration of a session); every consumer — a dashboard, an overlay, the Manager — **connects** as a client. Because PUB/SUB natively supports any number of subscribers on one bound endpoint, there is no separate multicast group or broadcast address to configure: adding a second consumer is just opening a second connection to the same `TcpHost:TcpPort`.

> **Note on the "slow joiner" behavior**: a SUB socket that has just connected can miss the very first message or two published right after connecting, until its subscription has propagated back to the PUB. This is a normal ZeroMQ characteristic (not a bug) and is harmless for a continuous telemetry stream — the next tick arrives a few milliseconds later.

---

## 2. Local Loopback (Same PC)

For dashboards, overlays, or SimHub-style apps running on the same PC as the game:

```json
{
  "isiMotor_RawUDP": {
    "TcpHost": "127.0.0.1",
    "TcpPort": "5000"
  }
}
```

Zero further configuration required. Any local Python client just does:

```python
from isimotor_rawudp_client import IsiMotorClient

client = IsiMotorClient(host="127.0.0.1", port=5000)
client.start()
```

---

## 3. LAN — Wi-Fi Tablet or Dashboard Device

To let a device elsewhere on the LAN (a tablet, a second PC) connect to the telemetry stream, bind the plugin's PUB socket on all interfaces (or its specific LAN IP) instead of loopback-only:

```json
{
  "isiMotor_RawUDP": {
    "TcpHost": "0.0.0.0",
    "TcpPort": "5000"
  }
}
```

On the receiving device, connect a SUB client to the game PC's LAN IP:

```python
client = IsiMotorClient(host="192.168.1.42", port=5000)  # game PC's LAN IP
client.start()
```

TCP handles retransmission and flow control itself, so there is no Wi-Fi-specific tuning needed (unlike UDP multicast/broadcast, which is sensitive to IGMP snooping and beacon rates on wireless networks).

---

## 4. Multiple Simultaneous Consumers

Because the plugin's telemetry socket is a ZeroMQ **PUB**, any number of SUB clients can connect to it at once — a motion rig, SimHub, a dashboard, and the Manager can all subscribe simultaneously without any extra plugin-side configuration:

```json
{
  "isiMotor_RawUDP": {
    "TcpHost": "0.0.0.0",
    "TcpPort": "5000"
  }
}
```

Each consumer independently does:

```python
client_a = IsiMotorClient(host="192.168.1.10", port=5000)  # motion rig
client_b = IsiMotorClient(host="192.168.1.10", port=5000)  # SimHub bridge
client_c = IsiMotorClient(host="192.168.1.10", port=5000)  # dashboard tablet
```

There is no practical limit imposed by the plugin; ZeroMQ's PUB socket fans the same message out to every connected subscriber.

---

## 5. Streaming Over Public IP / Internet / 4G

### Method A: VPN Mesh (Recommended) — Tailscale / WireGuard

The safest and simplest option for a remote pit-wall or coach setup: install [Tailscale](https://tailscale.com) (or WireGuard) on both the game PC and the remote engineer's machine. They get a private, encrypted `100.64.x.x`-range IP that behaves like a LAN address, with no port forwarding or public exposure.

```json
{
  "isiMotor_RawUDP": {
    "TcpHost": "0.0.0.0",
    "TcpPort": "5000"
  }
}
```

The remote engineer connects using the game PC's Tailscale IP:

```python
client = IsiMotorClient(host="100.64.1.25", port=5000)
```

### Method B: Direct Public IP & Port Forwarding (NAT)

If a VPN is not an option, you can expose the PUB endpoint directly over public IPv4 via router port forwarding:

```
┌──────────────────────┐       Internet        ┌──────────────────────┐    Port Forward     ┌──────────────────────┐
│  Sim Racer PC         │ ────────────────────> │ Remote Router Box     │ ──────────────────> │ Remote Engineer PC   │
│  TcpHost=0.0.0.0       │     (Public WAN)      │ Public IP: 82.64.x.y  │    TCP Port 5000     │ SUB connects here    │
└──────────────────────┘                       └──────────────────────┘                     └──────────────────────┘
```

1. **On the Sim Racer PC's router**: add a **Port Forwarding (NAT)** rule forwarding **TCP** port `5000` to the sim PC's LAN IP.
2. **Find the Sim Racer PC's public IP**: visit `https://ifconfig.me` from that PC.
3. **On the remote engineer's client**: connect to that public IP:
   ```python
   client = IsiMotorClient(host="82.64.x.y", port=5000)
   ```

> **Caution:**
> Direct TCP port forwarding exposes that port to the open internet. Anyone knowing the public IP can open a ZeroMQ SUB connection to the stream. For secure long-term remote team telemetry, **Method A (Tailscale/VPN)** is strongly advised.

### Method C: Relay / WebSocket Proxy for Web Dashboards

For multi-viewer web dashboards or race broadcast overlays, run a small relay process that connects to the plugin as a regular SUB client, then re-publishes over WebSockets to browsers:

```
┌─────────────┐   ZeroMQ PUB/SUB      ┌───────────────────────────┐   WebSockets / HTTP   ┌───────────────────┐
│ Sim Game PC │ ───────────────────> │ Cloud VPS (Relay Server)  │ ────────────────────> │ 100+ Web Viewers  │
└─────────────┘                      │ Python (isimotor client)  │                       │ Browser Overlays  │
                                     └───────────────────────────┘                       └───────────────────┘
```

The relay connects `IsiMotorClient(host="<sim-pc>", port=5000)` and forwards decoded packets (JSON or compact binary frames) to browsers over WebSockets.

---

## 6. Firewall & Troubleshooting Checklist

### Windows Firewall Configuration (Sim Racer PC)
If remote/LAN consumers cannot connect:

```powershell
New-NetFirewallRule -DisplayName "isiMotor ZeroMQ Telemetry (5000)" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "isiMotor ZeroMQ Inbound Commands (5001)" -Direction Inbound -LocalPort 5001 -Protocol TCP -Action Allow
```

### Linux Firewall Configuration

```bash
sudo ufw allow 5000/tcp
sudo ufw allow 5001/tcp
```

### Quick Diagnostic Commands

* **Verify the plugin's PUB socket is listening on port 5000**:
  * Windows: `netstat -ano | findstr :5000`
  * Linux: `ss -tlnp | grep 5000`
* **Inspect the live stream with the Manager**:
  ```bash
  isi-manager --host 127.0.0.1 --port 5000
  ```
* **Sniff the raw TCP handshake/traffic** (payload itself is ZeroMQ-framed binary, not human-readable):
  ```bash
  sudo tcpdump -i any -n tcp port 5000 -X
  ```
