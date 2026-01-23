# w55rp20_s2e_spi.py
# W55RP20-S2E SPI Master (MicroPython / RP2040 Pico)

from machine import SPI, Pin
import time
import gc

# -----------------------
# Pin map (Pico)
# -----------------------
SCK    = 2
MOSI   = 3
MISO   = 4
CS     = 5
INT    = 26
IF_SEL = 13      # High=SPI, Low=UART

# -----------------------
# SPI config
# -----------------------
SPI_ID    = 0
SPI_BAUD  = 50_000
POL       = 0
PHA       = 0

CS_HOLD_US = 2
CS_GAP_US  = 2

# -----------------------
# Protocol constants
# -----------------------
DUMMY = 0xFF
ACK   = 0x0A
NACK  = 0x0B
CMD_B0 = 0xB0
RSP_B1 = 0xB1

# -----------------------
# Timeouts / loop policy (SPI)
# -----------------------
INT_TIMEOUT_MS = 50
RX_TIMEOUT_MS  = 1500
ACK_TIMEOUT_MS = 1500

# GC config (Run every 30 calls)
GC_EVERY = 30
_gc_count = 0

# -----------------------
# Helpers
# -----------------------
def ticks_deadline(timeout_ms: int) -> int:
    return time.ticks_add(time.ticks_ms(), timeout_ms)

def timed_out(deadline: int) -> bool:
    return time.ticks_diff(time.ticks_ms(), deadline) >= 0

def hexdump(b: bytes, width: int = 16):
    for i in range(0, len(b), width):
        c = b[i:i+width]
        print("%04X  %-*s  %s" % (
            i,
            width * 3,
            " ".join("%02X" % x for x in c),
            "".join(chr(x) if 32 <= x <= 126 else "." for x in c),
        ))

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
# SPI bus init
# -----------------------
Pin(IF_SEL, Pin.OUT).value(1)      # Select SPI mode
time.sleep_ms(50)

cs   = Pin(CS, Pin.OUT, value=1)
intp = Pin(INT, Pin.IN, Pin.PULL_UP)

spi = SPI(
    SPI_ID,
    baudrate=SPI_BAUD,
    polarity=POL,
    phase=PHA,
    bits=8,
    firstbit=SPI.MSB,
    sck=Pin(SCK),
    mosi=Pin(MOSI),
    miso=Pin(MISO),
)

_tx1 = bytearray(1)
_rx1 = bytearray(1)

CAP_MAX = 2048
_RX_BUF = bytearray(CAP_MAX)
_RX_MV  = memoryview(_RX_BUF)

def xfer_byte(tx: int) -> int:
    _tx1[0] = tx & 0xFF
    cs.value(0)
    try:
        if CS_HOLD_US:
            time.sleep_us(CS_HOLD_US)
        spi.write_readinto(_tx1, _rx1)
        return _rx1[0]
    finally:
        cs.value(1)
        if CS_GAP_US:
            time.sleep_us(CS_GAP_US)

def wait_int_low(timeout_ms: int) -> bool:
    dl = ticks_deadline(timeout_ms)
    while not timed_out(dl):
        if intp.value() == 0:
            return True
        time.sleep_us(50)
    return False

def wait_ack(timeout_ms: int = 1500, max_bytes: int = 4096):
    dl = ticks_deadline(timeout_ms)
    cnt = 0
    while not timed_out(dl) and cnt < max_bytes:
        b = xfer_byte(DUMMY)
        cnt += 1
        if b == ACK:
            xfer_byte(DUMMY); xfer_byte(DUMMY); xfer_byte(DUMMY)
            return True
        if b == NACK:
            return False
    return None

def read_b1_payload(timeout_ms: int = 2000, scan_max: int = 8192):
    dl = ticks_deadline(timeout_ms)
    scanned = 0
    while not timed_out(dl) and scanned < scan_max:
        b = xfer_byte(DUMMY)
        scanned += 1
        if b == RSP_B1:
            len_l = xfer_byte(DUMMY)
            len_h = xfer_byte(DUMMY)
            _     = xfer_byte(DUMMY)
            length = len_l | (len_h << 8)

            if length == 0:
                return (_RX_MV[:0], 0)

            rd = length if length <= CAP_MAX else CAP_MAX
            for i in range(rd):
                _RX_BUF[i] = xfer_byte(DUMMY)
            for _i in range(length - rd):
                xfer_byte(DUMMY)
            return (_RX_MV[:rd], rd)
    return (None, 0)

# -----------------------
# AT GET / SET
# -----------------------
def at_get(cmd2: str, int_timeout_ms: int = 30, rx_timeout_ms: int = 2000):
    if len(cmd2) != 2:
        raise ValueError("AT GET supports only 2-character commands")
    xfer_byte(ord(cmd2[0]))
    xfer_byte(ord(cmd2[1]))
    xfer_byte(0x0D)
    xfer_byte(0x0A)
    wait_int_low(int_timeout_ms)
    mv, n = read_b1_payload(timeout_ms=rx_timeout_ms)
    return mv, n

def at_set(cmd: str, ack_timeout_ms: int = 1500):
    b = cmd.encode("ascii")
    if not b.endswith(b"\r\n"):
        b += b"\r\n"
    if len(b) < 2:
        raise ValueError("AT SET command too short")
    total_len = len(b)
    data_len = total_len - 2
    if data_len > 0xFFFF:
        raise ValueError("AT SET command too long")

    xfer_byte(b[0])
    xfer_byte(b[1])
    xfer_byte(data_len & 0xFF)
    xfer_byte((data_len >> 8) & 0xFF)

    r = wait_ack(timeout_ms=ack_timeout_ms)
    if r is None: raise RuntimeError("ACK timeout (AT header)")
    if r is False: raise RuntimeError("NACK (AT header)")

    for i in range(2, total_len):
        xfer_byte(b[i])

    r2 = wait_ack(timeout_ms=ack_timeout_ms)
    if r2 is None: raise RuntimeError("ACK timeout (AT payload)")
    if r2 is False: raise RuntimeError("NACK (AT payload)")
    return True

def _decode_resp_ascii(mv, n: int) -> str:
    raw = bytes(mv[:n])
    raw = raw.split(b"\x00", 1)[0]
    return raw.decode("ascii", "ignore")

def _parse_get_value(cmd: str, resp_ascii: str):
    s = resp_ascii.strip("\r\n")
    cu = cmd.upper()
    if s.upper().startswith(cu):
        tail = s[len(cu):]
    else:
        tail = s
    return tail.strip()

# -----------------------
# Public send_cmd() API
# -----------------------
def send_cmd(at_cmd: str, at_param: str):
    global _gc_count
    
    cmd = (at_cmd or "").strip()
    if not cmd:
        raise ValueError("at_cmd is empty")

    cmd_u = cmd.upper()
    if cmd_u in ("HELP", "?"):
        print_help()
        return {"type": "help", "ok": True}

    if at_param:
        cmdline = cmd + at_param
        ok = at_set(cmdline, ack_timeout_ms=ACK_TIMEOUT_MS)
        result = {"type": "set", "ok": bool(ok)}
    else:
        mv, n = at_get(cmd, int_timeout_ms=INT_TIMEOUT_MS, rx_timeout_ms=RX_TIMEOUT_MS)
        if mv is None or n <= 0:
            result = {"type": "get", "ok": False, "value": None, "raw": None}
        else:
            resp_ascii = _decode_resp_ascii(mv, n)
            value = _parse_get_value(cmd, resp_ascii)
            result = {"type": "get", "ok": True, "value": value, "raw": resp_ascii.strip("\r\n")}

    # [Modified] Run GC only once every N calls
    if GC_EVERY > 0:
        _gc_count += 1
        if _gc_count >= GC_EVERY:
            gc.collect()
            _gc_count = 0

    return result
    
def print_info():
    print("=== W55RP20-S2E SPI AT GET/SET test ===")
    print(f"SPI{SPI_ID} baud={SPI_BAUD} POL={POL} PHA={PHA}")
    print(f"Pins: SCK=GP{SCK} MOSI=GP{MOSI} MISO=GP{MISO} CS=GP{CS} INT=GP{INT} IF_SEL=GP{IF_SEL}")
    print(f"CS_HOLD_US={CS_HOLD_US}, CS_GAP_US={CS_GAP_US}")
    print(f"INT_TIMEOUT_MS={INT_TIMEOUT_MS}, RX_TIMEOUT_MS={RX_TIMEOUT_MS}, ACK_TIMEOUT_MS={ACK_TIMEOUT_MS}")