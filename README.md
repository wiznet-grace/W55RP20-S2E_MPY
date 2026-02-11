# W55RP20-S2E MicroPython Driver & Examples

> **GitHub Repository:** [https://github.com/wiznet-grace/W55RP20-S2E_MPY](https://github.com/wiznet-grace/W55RP20-S2E_MPY)

## 🇰🇷 [KR] 기술 설명서
RP2040 MicroPython 환경에서 **W55RP20-S2E** 모듈을 제어하기 위한 드라이버 상세 기술 문서입니다.

### 0. 개발 환경 (Environment)
> * **Master Board:** Raspberry Pi Pico (RP2040)
> * **Firmware:** MicroPython v1.27.0 Release

### 1. 폴더 및 파일 구조 (Directory Structure)

```text
W55RP20-S2E_MPY/
├── lib/                          # [Core] 드라이버 라이브러리
│   ├── w55rp20_s2e_spi.py
│   └── w55rp20_s2e_uart.py
│
└── examples/                     # [Apps] 실행 예제
    ├── 01_at_cmd_tester.py              # (Active) 기본 AT 명령 테스트
    ├── 02_tcp_client_loopback.py        # (Active) TCP 클라이언트 루프백
    ├── 03_tcp_server_loopback.py        # (Active) TCP 서버 루프백
    ├── 04_udp_loopback.py               # (Active) UDP 루프백
    ├── 05_http_client.py                # (Active) HTTP GET 요청
    ├── 06_web_server.py                 # (Active) 웹 서버
    └── 07_ssl_client.py                 # (Active) SSL/TLS 클라이언트
```

### 2. 예제 파일 상세 (Example Files)
| 파일명 (File) | 상태 (Status) | 설명 (Description) |
| :--- | :--- | :--- |
| **`01_at_cmd_tester.py`** | **Active** | • **기본 예제:** AT 커맨드 전송 및 응답 확인<br>• **모드 선택:** SPI/UART 설정 가능<br>• **안전장치:** `try-except` 적용됨 |
| **`02_tcp_client_loopback.py`** | **Active** | • TCP 클라이언트 루프백<br>• UART 모드 예제 |
| **`03_tcp_server_loopback.py`** | **Active** | • TCP 서버 루프백<br>• SPI/UART 지원 |
| **`04_udp_loopback.py`** | **Active** | • UDP 루프백 통신<br>• SPI/UART 지원 |
| **`05_http_client.py`** | **Active** | • HTTP GET 요청 예제<br>• httpbin.org 테스트<br>• SPI/UART 지원 |
| **`06_web_server.py`** | **Active** | • 웹 서버 예제<br>• TCP Server 모드<br>• HTML 응답 전송<br>• SPI/UART 지원 |
| **`07_ssl_client.py`** | **Active** | • SSL/TLS 클라이언트<br>• 암호화 통신<br>• 루프백 에코<br>• SPI/UART 지원 |

### 3. 하드웨어 구성 (Pin Configuration)

**① 모드 선택 (Mode Selection)**
| 핀 번호 (Pin) | 핀 이름 (Name) | 상태 (State) | 동작 모드 (Operation Mode) |
| :---: | :---: | :---: | :--- |
| **GP13** | **IF_SEL** | `HIGH` (3.3V) | **SPI Mode** |
| **GP13** | **IF_SEL** | `LOW` (GND) | **UART Mode** |

**② 통신 핀 맵 (Pin Map)**
| 기능 (Function) | Pico Pin | W55RP20 Pin | 비고 (Note) |
| :--- | :---: | :---: | :--- |
| **SPI Clock** | **GP2** | SCK | |
| **SPI TX** | **GP3** | MOSI | Master Out Slave In |
| **SPI RX** | **GP4** | MISO | Master In Slave Out |
| **SPI CS** | **GP5** | CS | Chip Select (Active Low) |
| **Interrupt** | **GP26** | INT | Active Low |
| **UART TX** | **GP4** | TXD | Pico TX → Module RX |
| **UART RX** | **GP5** | RXD | Pico RX ← Module TX |

> ⚠️ **주의:** GP4, GP5 핀은 SPI와 UART 모드에서 역할이 다릅니다. 사용 모드에 맞춰 배선을 확인하세요.|

---

## 🇺🇸 [EN] Technical Manual
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
```

### 2. Example Files List
| File Name | Status | Description |
| :--- | :--- | :--- |
| **`01_at_cmd_tester.py`** | **Active** | • **Basic:** Sends AT commands & checks responses<br>• **Mode:** Supports SPI/UART selection<br>• **Safety:** Includes `try-except` logic |
| **`02_tcp_client_loopback.py`** | **Active** | • TCP Client Loopback<br>• UART mode example |
| **`03_tcp_server_loopback.py`** | **Active** | • TCP Server Loopback<br>• SPI/UART support |
| **`04_udp_loopback.py`** | **Active** | • UDP Loopback<br>• SPI/UART support |
| **`05_http_client.py`** | **Active** | • HTTP GET Request<br>• httpbin.org test<br>• SPI/UART support |
| **`06_web_server.py`** | **Active** | • Web Server Example<br>• TCP Server mode<br>• Serves HTML response<br>• SPI/UART support |
| **`07_ssl_client.py`** | **Active** | • SSL/TLS Client<br>• Encrypted communication<br>• Loopback echo<br>• SPI/UART support |

### 3. Hardware Configuration

**① Mode Selection**
| Pin | Name | State | Operation Mode |
| :---: | :---: | :---: | :--- |
| **GP13** | **IF_SEL** | `HIGH` (3.3V) | **SPI Mode** |
| **GP13** | **IF_SEL** | `LOW` (GND) | **UART Mode** |

**② Pin Map**
| Function | Pico Pin | W55RP20 Pin | Note |
| :--- | :---: | :---: | :--- |
| **SPI Clock** | **GP2** | SCK | |
| **SPI TX** | **GP3** | MOSI | Master Out Slave In |
| **SPI RX** | **GP4** | MISO | Master In Slave Out |
| **SPI CS** | **GP5** | CS | Chip Select (Active Low) |
| **Interrupt** | **GP26** | INT | Active Low |
| **UART TX** | **GP4** | TXD | Pico TX → Module RX |
| **UART RX** | **GP5** | RXD | Pico RX ← Module TX |

> ⚠️ **Note:** GP4 and GP5 have different roles in SPI and UART modes. Check wiring accordingly.
