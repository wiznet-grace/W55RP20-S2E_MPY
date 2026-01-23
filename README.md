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
    ├── 02_loopback_tcp_server.py # (추가 예정)
    ├── 03_loopback_tcp_client.py # (추가 예정)
    ├── 04_loopback_udp.py        # (추가 예정)
    ├── 05_http_server.py         # (추가 예정)
    ├── 06_ssl_client.py          # (추가 예정)
    ├── 07_mqtt_client.py         # (추가 예정)
    └── 08_aws_iot_mqtt.py        # (추가 예정)
```

### 2. 예제 파일 상세 (Example Files)
| 파일명 (File) | 상태 (Status) | 설명 (Description) |
| :--- | :--- | :--- |
| **`01_at_cmd_tester.py`** | **Active** | • **기본 예제:** AT 커맨드 전송 및 응답 확인<br>• **모드 선택:** SPI/UART 설정 가능<br>• **안전장치:** `try-except` 적용됨 |
| `02_loopback_tcp_server.py` | *추가 예정* | TCP 서버 루프백 예제 |
| `03_loopback_tcp_client.py` | *추가 예정* | TCP 클라이언트 루프백 예제 |
| `04_loopback_udp.py` | *추가 예정* | UDP 통신 예제 |
| `05_http_server.py` | *추가 예정* | 웹 서버 구동 예제 |
| `06_ssl_client.py` | *추가 예정* | SSL/TLS 보안 접속 예제 |
| `07_mqtt_client.py` | *추가 예정* | MQTT 통신 예제 |
| `08_aws_iot_mqtt.py` | *추가 예정* | AWS IoT Core 연동 예제 |

### 3. 드라이버 주요 동작 (Driver Logic)
| 파일명 (File) | 역할 (Role) | 주요 동작 (Key Logic) |
| :--- | :--- | :--- |
| **`w55rp20_s2e_spi.py`** | SPI 드라이버 | • **프로토콜:** AT Frame 구조 및 Byte 단위 CS 제어<br>• **메모리:** `bytearray` 버퍼 재사용<br>• **최적화:** 30회 주기 자동 GC 수행 |
| **`w55rp20_s2e_uart.py`** | UART 드라이버 | • **전송:** 표준 ASCII (`CMD` + `\r\n`) 전송<br>• **수신:** Rolling Window 방식의 타임아웃 처리<br>• **최적화:** 30회 주기 자동 GC 수행 |

### 4. 하드웨어 구성 (Pin Configuration)

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

> ⚠️ **주의:** GP4, GP5 핀은 SPI와 UART 모드에서 역할이 다릅니다. 사용 모드에 맞춰 배선을 확인하세요.

### 5. 안정성 및 메모리 관리 (Stability & Memory)
장시간 구동 시 시스템 멈춤(Crash)을 방지하기 위해 아래 기술이 적용되었습니다.

| 구분 (Category) | 문제점 (Problem) | 해결책 (Solution) |
| :--- | :--- | :--- |
| **메모리 단편화** | 잦은 리스트 생성으로<br>인한 힙 메모리 부족 | • **Buffer Reuse:** 미리 할당된 `memoryview` 버퍼 사용<br>• **Periodic GC:** 트랜잭션 **30회마다 1회** GC 수행 |
| **통신 오류** | 노이즈로 인한<br>시스템 멈춤 | • **Fault Tolerance:** 실행 예제(`01_at_cmd.py`) 내<br>`try-except` 블록이 에러를 포착하고 자동 재시도 |

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
    ├── 02_loopback_tcp_server.py # (Planned)
    ├── 03_loopback_tcp_client.py # (Planned)
    ├── 04_loopback_udp.py        # (Planned)
    ├── 05_http_server.py         # (Planned)
    ├── 06_ssl_client.py          # (Planned)
    ├── 07_mqtt_client.py         # (Planned)
    └── 08_aws_iot_mqtt.py        # (Planned)
```

### 2. Example Files List
| File Name | Status | Description |
| :--- | :--- | :--- |
| **`01_at_cmd_tester.py`** | **Active** | • **Basic:** Sends AT commands & checks responses<br>• **Mode:** Supports SPI/UART selection<br>• **Safety:** Includes `try-except` logic |
| `02_loopback_tcp_server.py` | *Planned* | TCP Server Loopback |
| `03_loopback_tcp_client.py` | *Planned* | TCP Client Loopback |
| `04_loopback_udp.py` | *Planned* | UDP Communication |
| `05_http_server.py` | *Planned* | Web Server Implementation |
| `06_ssl_client.py` | *Planned* | SSL/TLS Secure Connection |
| `07_mqtt_client.py` | *Planned* | MQTT Client |
| `08_aws_iot_mqtt.py` | *Planned* | AWS IoT Core Integration |

### 3. Driver Logic
| File | Role | Key Logic |
| :--- | :--- | :--- |
| **`w55rp20_s2e_spi.py`** | SPI Driver | • **Protocol:** Handles AT Frames & CS toggling<br>• **Memory:** Reuses `bytearray` buffers<br>• **Optimization:** Auto-GC every 30 transactions |
| **`w55rp20_s2e_uart.py`** | UART Driver | • **Tx:** Sends standard ASCII (`CMD` + `\r\n`)<br>• **Rx:** Rolling Window mechanism with timeouts<br>• **Optimization:** Auto-GC every 30 transactions |

### 4. Hardware Configuration

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

### 5. Stability & Memory Management
The following techniques are applied to prevent system crashes during long-term operation.

| Category | Potential Issue | Applied Solution |
| :--- | :--- | :--- |
| **Fragmentation** | Heap exhaustion due to<br>frequent object creation | • **Buffer Reuse:** Uses pre-allocated `memoryview`<br>• **Periodic GC:** Calls `gc.collect()` every **30 cycles** |
| **Comm Error** | System freeze caused<br>by noise or timeout | • **Fault Tolerance:** `try-except` block in `01_at_cmd.py`<br>catches errors and triggers auto-retry |