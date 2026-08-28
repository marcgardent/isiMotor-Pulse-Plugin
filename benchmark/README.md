# isiMotor Telemetry Packet Sniffer & Frequency Benchmark (Textual TUI)

Modern, interactive terminal dashboard built with **[Textual](https://textual.textualize.io/)** for **Le Mans Ultimate** and **rFactor 2** binary telemetry streams.

---

## 🚀 Key Features

* **Interactive Textual TUI:**
  * **Header & Clock:** Live session duration, total packets, and instant bandwidth (KB/s & MB).
  * **Frequency & Jitter Table (DataTable):** Real-time Hz measurement (sliding 1s window), average delay (ms), jitter (±ms), and throughput per binary stream.
  * **Physics & Driver Input Gauges:** Visual progress bars for Throttle, Brake, Steering, plus 3D/ISO speed, RPM, Gear, Fuel, and Downforce.
  * **4 Wheels Matrix:** Surface temperatures (°C), Brake temperatures (°C), and live tire slip ratios.
  * **Scoring & Chronometer:** Track name, Lap counter, Sector, S1/S2 timing, Last lap, and Best lap.
* **Keyboard Shortcuts:**
  * `m` : Toggle built-in mock telemetry transmitter on/off (@ 100 Hz).
  * `r` : Reset counters and statistics.
  * `q` : Quit application cleanly.

---

## 🛠️ Usage

```bash
# Listen to live game telemetry on default port 5000:
python sniffer.py

# Run in test simulation mode (with mock data stream enabled):
python sniffer.py --mock

# Listen on custom host/port:
python sniffer.py --host 0.0.0.0 --port 5000
```
