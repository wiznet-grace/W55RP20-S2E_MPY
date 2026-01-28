# w55rp20_s2e_uart.py
# W55RP20-S2E UART Master (MicroPython / RP2040 Pico)
# [Zero-Copy Version] Optimized return types (int/tuple) to prevent GC.
# Aligned API with SPI driver for consistency.

from machine import UART, Pin
import time

# -----------------------
# Pin map / select pin
# -----------------------
MODE_SEL = 13      # High=SPI, Low=UART

# -----------------------
# UART config
# -----------------------
UART_ID = 1
UART_BAUD = 115200
UART_TX = 4      # GP4
UART_RX = 5      # GP5

# -----------------------
# Timeouts / loop policy
# -----------------------
UART_READ_WINDOW_MS = 200
UART_POLL_MS = 10

# -----------------------
# Error Codes (Synced with SPI)
# -----------------------
SUCCESS = 0
ERR_TIMEOUT = -2
ERR_UNKNOWN = -99

# -----------------------
# DATA RX buffer (avoid heap alloc on recv)
# -----------------------
CAP_MAX = 2048
_RX_BUF = bytearray(CAP_MAX)
_RX_MV  = memoryview(_RX_BUF)

# -----------------------
# HELP
# -----------------------
def print_help():
    print("=== W55RP20-S2E AT Help ===")
    print("Enter command mode: +++ (guard time >= 500ms before/after)")
    print("Exit command mode: EX")
    print("Save settings: SV  | Reboot: RT  | Factory reset: FR")
    print("")
    print("[Device Info] (RO)")
    print("MC  -> MAC address (ex: MC00:08:DC:00:00:01)")
    print("VR  -> Firmware version (ex: VR1.0.0)")
    print("MN  -> Product name (ex: MNWIZ5XXRSR-RP)")
    print("ST  -> Status (BOOT/OPEN/CONNECT/UPGRADE/ATMODE)")
    print("UN  -> UART interface str (ex: UNRS-232/TTL)")
    print("UI  -> UART interface code (ex: UI0)")
    print("")
    print("[Network] (RW)")
    print("OPx -> Mode: 0 TCP client, 1 TCP server, 2 mixed, 3 UDP, 4 SSL, 5 MQTT, 6 MQTTS")
    print("IMx -> IP alloc: 0 static, 1 DHCP")
    print("LIa.b.c.d -> Local IP (ex: LI192.168.11.2)")
    print("SMa.b.c.d -> Subnet (ex: SM255.255.255.0)")
    print("GWa.b.c.d -> Gateway (ex: GW192.168.11.1)")
    print("DSa.b.c.d -> DNS (ex: DS8.8.8.8)")
    print("LPn -> Local port (ex: LP5000)")
    print("RHa.b.c.d / domain -> Remote host (ex: RH192.168.11.3)")
    print("RPn -> Remote port (ex: RP5000)")
    print("")
    print("[UART] (RW)")
    print("BRx -> Baud (12=115200, 13=230400)")
    print("DBx -> Data bits (0=7bit, 1=8bit)")
    print("PRx -> Parity (0=None, 1=Odd, 2=Even)")
    print("SBx -> Stop bits (0=1bit, 1=2bit)")
    print("FLx -> Flow (0=None, 1=XON/XOFF, 2=RTS/CTS)")
    print("ECx -> Echo (0=Off, 1=On)")
    print("")
    print("[Packing] (RW)")
    print("PTn -> Time delimiter ms (ex: PT1000)")
    print("PSn -> Size delimiter bytes (ex: PS64)")
    print("PDxx -> Char delimiter hex (ex: PD0D)")
    print("")
    print("[Options] (RW)")
    print("ITn -> Inactivity sec (ex: IT30)")
    print("RIn -> Reconnect interval ms (ex: RI3000)")
    print("CPx -> Conn password enable (0/1)")
    print("NPxxxx -> Conn password (max 8 chars)")
    print("SPxxxx -> Search ID (max 8 chars)")
    print("DGx -> Debug msg (0/1)")
    print("KAx -> Keep-alive (0/1)")
    print("KIn -> KA initial interval ms (ex: KI7000)")
    print("KEn -> KA retry interval ms (ex: KE5000)")
    print("SOn -> SSL recv timeout ms (ex: SO2000)")
    print("")
    print("[MQTT] (RW)")
    print("QUuser QPpass QCid QK60 PUtopic")
    print("U0sub U1sub U2sub QO0")
    print("")
    print("Type HELP or ? to show this list again.")

# -----------------------
# UART init
# -----------------------
Pin(MODE_SEL, Pin.OUT).value(0)   # Select UART mode
time.sleep_ms(50)

uart = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX), rx=Pin(UART_RX), timeout=10)
time.sleep_ms(100)

def _read_response():
    buf = bytearray()
    deadline = time.ticks_add(time.ticks_ms(), UART_READ_WINDOW_MS)
    got_any = False

    while True:
        n = uart.any()
        if n:
            got_any = True
            data = uart.read(n)
            if data:
                buf.extend(data)
                deadline = time.ticks_add(time.ticks_ms(), UART_READ_WINDOW_MS)

        if got_any and time.ticks_diff(time.ticks_ms(), deadline) >= 0:
            break

        time.sleep_ms(UART_POLL_MS)
        if (not got_any) and time.ticks_diff(time.ticks_ms(), deadline) >= 0:
            break

    return bytes(buf) if buf else None

def _decode_resp_ascii(raw):
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw
    # MicroPython: no keyword args for errors=...
    return raw.decode("ascii", "ignore")

def _parse_get_value(cmd2, resp_ascii):
    if not resp_ascii:
        return None
    s = resp_ascii.strip()
    c = (cmd2 or "").strip().upper()
    if len(s) >= 2 and s[:2].upper() == c:
        return s[2:]
    return None

def _is_error_response(resp_ascii):
    if not resp_ascii:
        return False
    u = resp_ascii.upper()
    return ("ER" in u) or ("ERROR" in u) or ("INVALID" in u)

# -----------------------
# Public APIs
# -----------------------
def send_cmd(at_cmd: str, at_param: str):
    """
    UART AT command send.
    Returns tuple: (error_code, value)
      - Success: (0, value) or (0, None)
      - Failure: (negative_int, None)
    """
    cmd = (at_cmd or "").strip().upper()
    param = at_param or ""

    if cmd in ("HELP", "?"):
        print_help()
        return (SUCCESS, None)

    try:
        # Flush stale RX
        while uart.any():
            uart.read()

        if param:
            # SET Command
            line = (cmd + param + "\r\n").encode("ascii")
            uart.write(line)
            raw = _read_response()
            resp_ascii = _decode_resp_ascii(raw)

            if resp_ascii is None:
                # No response (might be okay for some cmds, or timeout)
                return (SUCCESS, None) 
            else:
                if _is_error_response(resp_ascii):
                    return (ERR_UNKNOWN, None)
                # For SET, we usually just return Success
                return (SUCCESS, None) 
        else:
            # GET Command
            line = (cmd + "\r\n").encode("ascii")
            uart.write(line)
            raw = _read_response()
            resp_ascii = _decode_resp_ascii(raw)

            if not resp_ascii:
                return (ERR_TIMEOUT, None)
            
            value = _parse_get_value(cmd, resp_ascii)
            if value is None:
                return (ERR_UNKNOWN, resp_ascii.strip()) # Return raw if parse failed
            
            return (SUCCESS, value)

    except Exception as e:
        print(f"[UART ERR] {e}")
        return (ERR_UNKNOWN, None)

def recv_data_mv():
    """
    Non-blocking DATA receive (Zero-Copy).
    returns: (memoryview, length)
    """
    n = uart.readinto(_RX_BUF)   # No allocation
    if not n:
        return (None, 0)
    return (_RX_MV, n)

def send_data(payload, length=None):
    """
    UART data send.
    Returns: 0 on Success (to match SPI driver signature)
    """
    if payload is None:
        return 0

    if isinstance(payload, str):
        payload = payload.encode("ascii")

    if length is None:
        uart.write(payload)
    else:
        uart.write(payload[:length])
        
    return SUCCESS # Always success for UART unless exception

def recv_data():
    """
    Legacy wrapper for compatibility with SPI driver structure.
    Returns: (mv, n) or None
    """
    # Just redirect to optimized version
    mv, n = recv_data_mv()
    if n > 0:
        return (mv, n)
    return None

def print_info():
    print("=== W55RP20-S2E UART Master ===")
    print(f"UART{UART_ID} baud={UART_BAUD} TX=GP{UART_TX} RX=GP{UART_RX}")
    print(f"Buffer CAP_MAX={CAP_MAX}")
