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
        print_help()
        return {"type": "help", "ok": True}

    result = {}
    try:
        # [Added] Flush: Clear any residual data in the RX buffer before sending a command
        while uart.any():
            uart.read()

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