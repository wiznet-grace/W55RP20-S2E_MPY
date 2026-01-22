# w55rp20_s2e_uart.py
# W55RP20-S2E UART Master (MicroPython / RP2040 Pico)

from machine import UART, Pin
import time
import gc

# -----------------------
# Pin map / select pin
# -----------------------
IF_SEL = 13      # High=SPI, Low=UART

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
# HELP
# -----------------------
def printHelp():
    print("=== W55RP20-S2E AT Help ===")
    print("Enter command mode: +++")
    print("Exit command mode: EX")
    # (Content omitted for brevity)
    print("Type HELP or ? to show this list again.")

# -----------------------
# UART init
# -----------------------
Pin(IF_SEL, Pin.OUT).value(0)   # Select UART mode
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
    if raw is None: return None
    if isinstance(raw, str): return raw
    return raw.decode("ascii", "ignore")

def _parse_get_value(cmd2, resp_ascii):
    if not resp_ascii: return None
    s = resp_ascii.strip()
    c = (cmd2 or "").strip().upper()
    if len(s) >= 2 and s[:2].upper() == c:
        return s[2:]
    return None

def _is_error_response(resp_ascii):
    if not resp_ascii: return False
    u = resp_ascii.upper()
    return ("ER" in u) or ("ERROR" in u) or ("INVALID" in u)

# -----------------------
# Public send_cmd() API
# -----------------------
def send_cmd(at_cmd: str, at_param: str):
    global _gc_count

    cmd = (at_cmd or "").strip().upper()
    param = at_param or ""

    if cmd in ("HELP", "?"):
        printHelp()
        return {"type": "help", "ok": True}

    result = {}
    try:
        if param:
            # SET
            line = (cmd + param + "\r\n").encode("ascii")
            uart.write(line)
            raw = _read_response()
            resp_ascii = _decode_resp_ascii(raw)
            
            # SET might not return a response:
            # - If no response, assume ok=True (adjust policy if needed)
            # - If response exists, check for error patterns
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

    # [Modified] Run GC only once every N calls
    if GC_EVERY > 0:
        _gc_count += 1
        if _gc_count >= GC_EVERY:
            gc.collect()
            _gc_count = 0
            
    return result

def print_info():
    print("=== W55RP20-S2E UART AT test ===")
    print(f"UART{UART_ID} baud={UART_BAUD} TX=GP{UART_TX} RX=GP{UART_RX} IF_SEL=GP{IF_SEL}(LOW=UART)")