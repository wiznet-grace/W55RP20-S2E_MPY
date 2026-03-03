
# W55RP20-S2E MicroPython Driver & Examples

> This repository is a reference example for the [WOW (Wiz of Wiznetian) Contest](https://maker.wiznet.io/contest/wow). For contest details and more information, see the contest page above.

**GitHub Repository:** [https://github.com/wiznet-grace/W55RP20-S2E_MPY](https://github.com/wiznet-grace/W55RP20-S2E_MPY)

## Technical Manual
Detailed technical documentation for the W55RP20-S2E module driver on RP2040 MicroPython.

### 0. Environment
> * **Master Board:** Raspberry Pi Pico (RP2040)
> * **Firmware:** MicroPython v1.27.0 Release

### 1. Directory Structure

```text
W55RP20-S2E_MPY/
├── lib/                          # [Core] Driver Libraries
│   ├── w55rp20_s2e_spi.py
│   └── w55rp20_s2e_uart.py
│
└── examples/                     # [Apps] Example Applications
    ├── 01_at_cmd_tester.py              # (Active) Basic AT Command Test
    ├── 02_tcp_client_loopback.py        # (Active) TCP Client Loopback (UART)
    ├── 03_tcp_server_loopback.py        # (Active) TCP Server Loopback
    ├── 04_udp_loopback.py               # (Active) UDP Loopback
    ├── 05_http_client.py                # (Active) HTTP GET Request
    ├── 06_web_server.py                 # (Active) Web Server
    └── 07_ssl_client.py                 # (Active) SSL/TLS Client
    ├── 08_mqtt_client.py                # (Active) MQTT Client
    ├── 09_mqtts_client.py               # (Active) MQTTS (SSL) Client
```

### 2. Example Files List
| File Name | Status | Description |
| :--- | :--- | :--- |
| **`01_at_cmd_tester.py`** | **Active** | • **Basic:** Sends AT commands & checks responses<br>• **Mode:** Supports SPI/UART selection<br>|
| **`02_tcp_client_loopback.py`** | **Active** | • TCP Client Loopback<br>• UART mode example |
| **`03_tcp_server_loopback.py`** | **Active** | • TCP Server Loopback<br>• SPI/UART support |
| **`04_udp_loopback.py`** | **Active** | • UDP Loopback<br>• SPI/UART support |
| **`05_http_client.py`** | **Active** | • HTTP GET Request<br>• httpbin.org test<br>• SPI/UART support |
| **`06_web_server.py`** | **Active** | • Web Server Example<br>• TCP Server mode<br>• Serves HTML response<br>• SPI/UART support |
| **`07_ssl_client.py`** | **Active** | • SSL/TLS Client<br>• Encrypted communication<br>• Loopback echo<br>• SPI/UART support |
| **`08_mqtt_client.py`** | **Active** | • MQTT Client<br>• Connects to MQTT broker<br>• Publishes and subscribes topics<br>• SPI/UART support |
| **`09_mqtts_client.py`** | **Active** | • MQTTS (SSL) Client<br>• Secure MQTT over TLS<br>• Publishes and subscribes topics<br>• SPI/UART support |

### 3. Hardware Configuration

**Mode Selection**
| Pin | Name | State | Operation Mode |
| :---: | :---: | :---: | :--- |
| **GP13** | **IF_SEL** | `HIGH` (3.3V) | **SPI Mode** |
| **GP13** | **IF_SEL** | `LOW` (GND) | **UART Mode** |

> ⚠️ **Note:** GP4 and GP5 have different roles in SPI and UART modes. Check wiring accordingly.

**UART Mode Pin Mapping:**
| Raspberry Pi Pico | W55RP20 EVB Pico |
| :---: | :---: |
| GPIO4 (UART_TX) | GPIO5 (UART_RX) |
| GPIO5 (UART_RX) | GPIO4 (UART_TX) |
| GPIO13 (MODE_SEL) | GPIO13 (MODE_SEL) |
| GND | GND |

**SPI Mode Pin Mapping:**
| Raspberry Pi Pico (Master) | W55RP20 EVB Pico (Slave) |
| :---: | :---: |
| GPIO2 (SPI_CLK) | GPIO2 (SPI_CLK) |
| GPIO3 (SPI_TX) | GPIO4 (SPI_RX) |
| GPIO4 (SPI_RX) | GPIO3 (SPI_TX) |
| GPIO5 (SPI_CS) | GPIO5 (SPI_CS) |
| GPIO26 (SPI_INT) | GPIO26 (SPI_INT) |
| GPIO13 (MODE_SEL) | GPIO13 (MODE_SEL) |
| GND | GND |
