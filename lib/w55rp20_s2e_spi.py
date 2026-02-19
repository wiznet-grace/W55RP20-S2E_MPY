# w55rp20_s2e_spi.py
# W55RP20-S2E SPI Master (MicroPython / RP2040 Pico)
# [Zero-Copy Version] Optimized return types (int/tuple) to prevent GC.

from machine import SPI, Pin
import time

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
DEBUG_PRINT = True

# Pin map (Pico)
SCK      = 2
MOSI     = 3
MISO     = 4
CS       = 5
INT      = 26
MODE_SEL = 13       # High=SPI, Low=UART

# SPI config
SPI_ID    = 0
SPI_BAUD  = 10_000_000
POL       = 0
PHA       = 0

# Tuning: Critical Timing Constants
CS_HOLD_US      = 2
CS_GAP_US       = 20
INT_CS_DELAY_US = 200

# -----------------------
# Protocol constants
# -----------------------
DUMMY      = 0xFF
ACK        = 0x0A
NACK       = 0x0B
CMD_B0     = 0xB0
RSP_B1     = 0xB1
DATA_TX_A0 = 0xA0

# -----------------------
# Error codes
# -----------------------
SUCCESS          =  0
ERR_NACK         = -1
ERR_TIMEOUT      = -2
ERR_INVALID_HEADER = -3
ERR_UNKNOWN      = -99

class S2EError(Exception):
    def __init__(self, msg: str, err_code: int, stage: str = None):
        super().__init__(msg)
        self.err_code = err_code
        self.stage    = stage

# -----------------------
# Timeouts / Polling (single source of truth)
# -----------------------
TIMEOUT_MS     = 2000   # Common timeout for ACK and RX (ms)
INT_TIMEOUT_MS = 10     # INT pin polling wait (ms) - used in recv_data loop
ACK_MAX_POLL   = 65535  # Max ACK poll count (covers MQTTS/SSL slow ACK)
DATA_SCAN_MAX  = 16384  # Max bytes to scan for B1 header in RX

# -----------------------
# SPI Primitives
# -----------------------
_tx1    = bytearray(1)
_rx1    = bytearray(1)
CAP_MAX = 2048
_RX_BUF = bytearray(CAP_MAX)
_RX_MV  = memoryview(_RX_BUF)

def xfer_byte(tx: int) -> int:
    """Single-byte SPI transaction with CS toggle. W55RP20-S2E requires CS toggle per byte."""
    _tx1[0] = tx & 0xFF
    cs.value(0)
    try:
        if CS_HOLD_US: time.sleep_us(CS_HOLD_US)
        spi.write_readinto(_tx1, _rx1)
        return _rx1[0]
    finally:
        cs.value(1)
        if CS_GAP_US: time.sleep_us(CS_GAP_US)

# -----------------------
# Helpers
# -----------------------
def ticks_deadline(timeout_ms: int) -> int:
    return time.ticks_add(time.ticks_ms(), timeout_ms)

def timed_out(deadline: int) -> bool:
    return time.ticks_diff(time.ticks_ms(), deadline) >= 0

def wait_int_low(timeout_ms: int = INT_TIMEOUT_MS) -> bool:
    if intp.value() == 0:
        return True
    dl = ticks_deadline(timeout_ms)
    while not timed_out(dl):
        if intp.value() == 0:
            return True
    return False

def wait_ack(timeout_ms: int = TIMEOUT_MS, max_bytes: int = ACK_MAX_POLL):
    dl  = ticks_deadline(timeout_ms)
    cnt = 0
    while not timed_out(dl) and cnt < max_bytes:
        b    = xfer_byte(DUMMY)
        cnt += 1
        if b == ACK:
            xfer_byte(DUMMY); xfer_byte(DUMMY); xfer_byte(DUMMY)
            return True
        if b == NACK:
            xfer_byte(DUMMY); xfer_byte(DUMMY); xfer_byte(DUMMY)
            return False
    return None

def read_b1_payload_status(timeout_ms: int = TIMEOUT_MS, scan_max: int = DATA_SCAN_MAX):
    dl      = ticks_deadline(timeout_ms)
    scanned = 0
    while not timed_out(dl) and scanned < scan_max:
        b        = xfer_byte(DUMMY)
        scanned += 1

        if b == NACK:
            xfer_byte(DUMMY); xfer_byte(DUMMY); xfer_byte(DUMMY)
            return (None, 0, ERR_NACK, "wait_b1")

        if b == RSP_B1:
            len_l  = xfer_byte(DUMMY)
            len_h  = xfer_byte(DUMMY)
            _      = xfer_byte(DUMMY)
            length = len_l | (len_h << 8)

            if length == 0:
                return (_RX_MV[:0], 0, SUCCESS, None)

            rd = length if length <= CAP_MAX else CAP_MAX
            for i in range(rd):
                _RX_BUF[i] = xfer_byte(DUMMY)
            for _ in range(length - rd):
                xfer_byte(DUMMY)
            return (_RX_MV[:rd], rd, SUCCESS, None)

    return (None, 0, ERR_TIMEOUT, "wait_b1")

def read_b1_payload(timeout_ms: int = TIMEOUT_MS, scan_max: int = DATA_SCAN_MAX):
    """Legacy helper for AT CMD (returns tuple only)."""
    mv, n, code, _ = read_b1_payload_status(timeout_ms, scan_max)
    return (mv, n)

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
Pin(MODE_SEL, Pin.OUT).value(1)
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

# -----------------------
# AT GET / SET
# -----------------------
def at_get(cmd2: str, timeout_ms: int = TIMEOUT_MS):
    if len(cmd2) != 2: raise ValueError("AT GET supports only 2-character commands")
    xfer_byte(ord(cmd2[0])); xfer_byte(ord(cmd2[1])); xfer_byte(0x0D); xfer_byte(0x0A)
    wait_int_low(timeout_ms)
    mv, n = read_b1_payload(timeout_ms)
    return mv, n

def at_set(cmd: str, timeout_ms: int = TIMEOUT_MS):
    b = cmd.encode("ascii")
    if not b.endswith(b"\r\n"): b += b"\r\n"
    total_len = len(b); data_len = total_len - 2
    xfer_byte(b[0]); xfer_byte(b[1]); xfer_byte(data_len & 0xFF); xfer_byte((data_len >> 8) & 0xFF)

    r = wait_ack(timeout_ms)
    if r is None:  raise RuntimeError("ACK timeout (AT header)")
    if r is False: raise RuntimeError("NACK (AT header)")

    for i in range(2, total_len): xfer_byte(b[i])

    r2 = wait_ack(timeout_ms)
    if r2 is None:  raise RuntimeError("ACK timeout (AT payload)")
    if r2 is False: raise RuntimeError("NACK (AT payload)")
    return True

# -----------------------
# DATA TX/RX
# -----------------------
def data_send(payload, timeout_ms: int = TIMEOUT_MS):
    if payload is None: payload = b""
    if isinstance(payload, str): payload = payload.encode("ascii")
    ln = len(payload)
    xfer_byte(DATA_TX_A0); xfer_byte(ln & 0xFF); xfer_byte((ln >> 8) & 0xFF); xfer_byte(DUMMY)

    r = wait_ack(timeout_ms)
    if r is None:  raise S2EError("ACK timeout (DATA header)", ERR_TIMEOUT, "data_header_ack")
    if r is False: raise S2EError("NACK (DATA header)",        ERR_NACK,    "data_header_ack")

    for b in payload: xfer_byte(b)

    r2 = wait_ack(timeout_ms)
    if r2 is None:  raise S2EError("ACK timeout (DATA payload)", ERR_TIMEOUT, "data_payload_ack")
    if r2 is False: raise S2EError("NACK (DATA payload)",        ERR_NACK,    "data_payload_ack")
    return True

def data_recv(timeout_ms: int = TIMEOUT_MS, scan_max: int = DATA_SCAN_MAX):
    if not wait_int_low(INT_TIMEOUT_MS): return None
    if INT_CS_DELAY_US: time.sleep_us(INT_CS_DELAY_US)
    xfer_byte(CMD_B0); xfer_byte(DUMMY); xfer_byte(DUMMY); xfer_byte(DUMMY)
    mv, n, err_code, stage = read_b1_payload_status(timeout_ms, scan_max)
    if err_code != SUCCESS:
        msg = "RX Timeout" if err_code == ERR_TIMEOUT else "RX NACK"
        raise S2EError(msg, err_code, stage)
    return (mv, n)

# -----------------------
# Public API Helpers
# -----------------------
def _decode_resp_ascii(mv, n: int) -> str:
    raw = bytes(mv[:n]).split(b"\x00", 1)[0]
    return raw.decode("ascii", "ignore")

def _parse_get_value(cmd: str, resp_ascii: str):
    s  = resp_ascii.strip("\r\n")
    cu = cmd.upper()
    return s[len(cu):].strip() if s.upper().startswith(cu) else s.strip()

_NO_PARAM_SET_CMDS = ("SV", "RT", "FR", "EX")

# -----------------------
# Public APIs
# -----------------------
def send_cmd(at_cmd: str, at_param: str):
    """
    Returns (error_code, value)
    - Success GET: (0, value_string)
    - Success SET: (0, None)
    - Failure:     (negative_int, None)
    """
    try:
        cmd = (at_cmd or "").strip()
        if not cmd: return (ERR_UNKNOWN, None)

        if cmd.upper() in ("HELP", "?"):
            print_help()
            return (SUCCESS, None)

        if at_param or (cmd in _NO_PARAM_SET_CMDS):
            at_set(cmd + (at_param or ""), timeout_ms=TIMEOUT_MS)
            return (SUCCESS, None)
        else:
            mv, n = at_get(cmd, timeout_ms=TIMEOUT_MS)
            if mv is None or n <= 0:
                return (ERR_UNKNOWN, None)
            val = _parse_get_value(cmd, _decode_resp_ascii(mv, n))
            return (SUCCESS, val)

    except RuntimeError:
        return (ERR_TIMEOUT, None)
    except Exception as e:
        if DEBUG_PRINT: print(f"[CMD ERR] {e}")
        return (ERR_UNKNOWN, None)

def send_data(payload):
    """
    Returns 0 on success, negative error code on failure.
    """
    try:
        data_send(payload, timeout_ms=TIMEOUT_MS)
        return SUCCESS
    except S2EError as e:
        if DEBUG_PRINT: print(f"[TX ERR] {e.stage}: {e} (Code: {e.err_code})")
        return e.err_code
    except Exception as e:
        if DEBUG_PRINT: print(f"[TX ERR] System Exception: {e}")
        return ERR_UNKNOWN

def recv_data():
    """
    Returns:
    - (memoryview, length) on success
    - None if no data
    - negative int on error
    """
    try:
        res = data_recv(timeout_ms=TIMEOUT_MS, scan_max=DATA_SCAN_MAX)
        return res  # (mv, n) or None
    except S2EError as e:
        if DEBUG_PRINT: print(f"[RX ERR] {e.stage}: {e} (Code: {e.err_code})")
        return e.err_code
    except Exception as e:
        if DEBUG_PRINT: print(f"[RX ERR] System Exception: {e}")
        return ERR_UNKNOWN

def print_info():
    print("=== W55RP20-S2E SPI Master ===")
    print(f"SPI{SPI_ID} baud={SPI_BAUD} POL={POL} PHA={PHA}")
    print(f"CS_HOLD_US={CS_HOLD_US}, CS_GAP_US={CS_GAP_US}, INT_CS_DELAY_US={INT_CS_DELAY_US}")
    print(f"TIMEOUT_MS={TIMEOUT_MS}, ACK_MAX_POLL={ACK_MAX_POLL}, DATA_SCAN_MAX={DATA_SCAN_MAX}")

