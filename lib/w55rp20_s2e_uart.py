# w55rp20_s2e_uart.py
# W55RP20-S2E UART Master (MicroPython / RP2040 Pico)

from machine import UART, Pin
import time
import gc

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

# GC config (Run every 30 calls)
GC_EVERY = 30
_gc_count = 0

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
    - HELP/? prints help.
    - SET: cmd+param+CRLF
    - GET: cmd+CRLF
    Return dict:
      - {"type":"get","ok":bool,"value":...,"raw":...}
      - {"type":"set","ok":bool,"raw":...}
    """
    global _gc_count

    cmd = (at_cmd or "").strip().upper()
    param = at_param or ""

    if cmd in ("HELP", "?"):
        print_help()
        return {"type": "help", "ok": True}

    result = {}
    try:
        # Flush stale RX
        while uart.any():
            uart.read()

        if param:
            # SET
            line = (cmd + param + "\r\n").encode("ascii")
            uart.write(line)
            raw = _read_response()
            resp_ascii = _decode_resp_ascii(raw)

            if resp_ascii is None:
                ok = True
                raw_out = None
            else:
                ok = not _is_error_response(resp_ascii)
                raw_out = resp_ascii.strip()
            result = {"type": "set", "ok": bool(ok), "raw": raw_out}
        else:
            # GET
            line = (cmd + "\r\n").encode("ascii")
            uart.write(line)
            raw = _read_response()
            resp_ascii = _decode_resp_ascii(raw)

            if not resp_ascii:
                result = {"type": "get", "ok": False, "value": None, "raw": None}
            else:
                value = _parse_get_value(cmd, resp_ascii)
                result = {
                    "type": "get",
                    "ok": value is not None,
                    "value": value,
                    "raw": resp_ascii.strip(),
                }

    except Exception as e:
        result = {"type": "error", "ok": False, "error_type": str(type(e)), "error": str(e)}

    # GC throttled
    if GC_EVERY > 0:
        _gc_count += 1
        if _gc_count >= GC_EVERY:
            gc.collect()
            _gc_count = 0

    return result

CAP_MAX = 2048
_RX_BUF = bytearray(CAP_MAX)
_RX_MV  = memoryview(_RX_BUF)

# DATA GC config (separate from send_cmd GC)
DATA_GC_EVERY = 2000   # DATA 루프에서 너무 자주 GC하면 지연 커짐. 적당히 크게.
_data_gc_cnt = 0

def recv_data_mv():
    """
    Non-blocking DATA receive (zero-allocation style).
    returns: (memoryview, length) or (None, 0)

    - IMPORTANT: memoryview는 _RX_BUF를 그대로 가리킴.
      다음 recv에서 내용이 덮어써지므로, 바로 처리/전송해야 함.
    """
    global _data_gc_cnt

    n = uart.readinto(_RX_BUF)   # no allocation for payload buffer
    if not n:
        # GC throttle (even when no data, keep it very light)
        _data_gc_cnt += 1
        if DATA_GC_EVERY > 0 and _data_gc_cnt >= DATA_GC_EVERY:
            gc.collect()
            _data_gc_cnt = 0
        return (None, 0)

    # GC throttle (when data exists)
    _data_gc_cnt += 1
    if DATA_GC_EVERY > 0 and _data_gc_cnt >= DATA_GC_EVERY:
        gc.collect()
        _data_gc_cnt = 0

    return (_RX_MV, n)


def send_data(payload, length=None):
    """
    UART data send (raw stream).
    payload: bytes/str/memoryview
    length: if payload is memoryview, send only first 'length' bytes without making big copies.
    """
    if payload is None:
        return 0

    if isinstance(payload, str):
        payload = payload.encode("ascii")

    if length is None:
        return uart.write(payload)

    # length given (typically payload is memoryview)
    # NOTE: payload[:length] creates a small memoryview object,
    # but only when real data exists (not every loop).
    return uart.write(payload[:length])

def recv_data():
    """
    Non-blocking DATA receive using pre-allocated buffer (no heap alloc per call).
    Return dict (SPI-style):
      {"type":"data_rx","ok":True,"mv":memoryview,"len":n}
      {"type":"data_rx","ok":False,"mv":None,"len":0}
    """
    n = uart.readinto(_RX_BUF)
    if not n:
        return {"type": "data_rx", "ok": False, "mv": None, "len": 0}
    return {"type": "data_rx", "ok": True, "mv": _RX_MV[:n], "len": n}

def print_info():
    print("=== W55RP20-S2E UART AT test ===")
    print(f"UART{UART_ID} baud={UART_BAUD} TX=GP{UART_TX} RX=GP{UART_RX} MODE_SEL=GP{MODE_SEL}(LOW=UART)")
    print(f"DATA CAP_MAX={CAP_MAX} UART_READ_WINDOW_MS={UART_READ_WINDOW_MS} UART_POLL_MS={UART_POLL_MS} GC_EVERY={GC_EVERY}")

