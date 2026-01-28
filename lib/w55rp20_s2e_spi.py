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
CS_HOLD_US = 2
CS_GAP_US  = 20       # Inter-transfer delay for stability
INT_CS_DELAY_US = 200 # Delay after INT low to allow module preparation

# -----------------------
# Protocol constants
# -----------------------
DUMMY = 0xFF
ACK   = 0x0A
NACK  = 0x0B
CMD_B0 = 0xB0
RSP_B1 = 0xB1
DATA_TX_A0 = 0xA0  # Master Write Data Length (DATA TX)

# -----------------------
# Error codes
# -----------------------
SUCCESS = 0
ERR_NACK = -1
ERR_TIMEOUT = -2
ERR_INVALID_HEADER = -3
ERR_UNKNOWN = -99

class S2EError(Exception):
    """Internal exception carrying an error code (C-style)."""
    def __init__(self, msg: str, err_code: int, stage: str = None):
        super().__init__(msg)
        self.err_code = err_code
        self.stage = stage

# -----------------------
# Timeouts / loop policy
# -----------------------
INT_TIMEOUT_MS = 200
RX_TIMEOUT_MS  = 2000
ACK_TIMEOUT_MS = 2000

# DATA RX/TX tuning
DATA_POLL_WAIT_MS = 10   # Short wait time for polling loop responsiveness
DATA_SCAN_MAX     = 16384

# -----------------------
# SPI Primitives
# -----------------------
_tx1 = bytearray(1)
_rx1 = bytearray(1)
CAP_MAX = 2048
_RX_BUF = bytearray(CAP_MAX)
_RX_MV  = memoryview(_RX_BUF)

def xfer_byte(tx: int) -> int:
    """Byte-by-byte transfer (Used for polling ACK/Status)."""
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

def wait_int_low(timeout_ms: int) -> bool:
    """
    Checks INT pin. If low, returns True immediately.
    Otherwise polls until timeout.
    """
    if intp.value() == 0:
        return True
    dl = ticks_deadline(timeout_ms)
    while not timed_out(dl):
        if intp.value() == 0:
            return True
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
            xfer_byte(DUMMY); xfer_byte(DUMMY); xfer_byte(DUMMY)
            return False
    return None

def read_b1_payload_status(timeout_ms: int = 2000, scan_max: int = 8192):
    """
    Helper for DATA RX. Returns tuple with status code.
    returns: (memoryview, length, err_code, stage)
    """
    dl = ticks_deadline(timeout_ms)
    scanned = 0
    while not timed_out(dl) and scanned < scan_max:
        b = xfer_byte(DUMMY)
        scanned += 1

        if b == NACK:
            xfer_byte(DUMMY); xfer_byte(DUMMY); xfer_byte(DUMMY)
            return (None, 0, ERR_NACK, "wait_b1")

        if b == RSP_B1:
            len_l = xfer_byte(DUMMY)
            len_h = xfer_byte(DUMMY)
            _     = xfer_byte(DUMMY)  # dummy 0xFF
            length = len_l | (len_h << 8)

            if length == 0:
                return (_RX_MV[:0], 0, SUCCESS, None)

            rd = length if length <= CAP_MAX else CAP_MAX
            for i in range(rd):
                _RX_BUF[i] = xfer_byte(DUMMY)
            for _i in range(length - rd):
                xfer_byte(DUMMY)
            return (_RX_MV[:rd], rd, SUCCESS, None)

    return (None, 0, ERR_TIMEOUT, "wait_b1")

def read_b1_payload(timeout_ms: int = 2000, scan_max: int = 8192):
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
    # ... (Help messages omitted for brevity) ...

# -----------------------
# SPI bus init
# -----------------------
Pin(MODE_SEL, Pin.OUT).value(1)      # Select SPI mode
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
def at_get(cmd2: str, int_timeout_ms: int = 30, rx_timeout_ms: int = 2000):
    if len(cmd2) != 2: raise ValueError("AT GET supports only 2-character commands")
    xfer_byte(ord(cmd2[0])); xfer_byte(ord(cmd2[1])); xfer_byte(0x0D); xfer_byte(0x0A)
    wait_int_low(int_timeout_ms)
    mv, n = read_b1_payload(timeout_ms=rx_timeout_ms)
    return mv, n

def at_set(cmd: str, ack_timeout_ms: int = 1500):
    b = cmd.encode("ascii")
    if not b.endswith(b"\r\n"): b += b"\r\n"
    total_len = len(b); data_len = total_len - 2
    xfer_byte(b[0]); xfer_byte(b[1]); xfer_byte(data_len & 0xFF); xfer_byte((data_len >> 8) & 0xFF)
    
    r = wait_ack(timeout_ms=ack_timeout_ms)
    if r is None: raise RuntimeError("ACK timeout (AT header)")
    if r is False: raise RuntimeError("NACK (AT header)")

    for i in range(2, total_len): xfer_byte(b[i])

    r2 = wait_ack(timeout_ms=ack_timeout_ms)
    if r2 is None: raise RuntimeError("ACK timeout (AT payload)")
    if r2 is False: raise RuntimeError("NACK (AT payload)")
    return True

# -----------------------
# DATA TX/RX (Core Logic)
# -----------------------
def data_send(payload, ack_timeout_ms: int = ACK_TIMEOUT_MS):
    if payload is None: payload = b""
    if isinstance(payload, str): payload = payload.encode("ascii")
    ln = len(payload)
    xfer_byte(DATA_TX_A0); xfer_byte(ln & 0xFF); xfer_byte((ln >> 8) & 0xFF); xfer_byte(DUMMY)
    r = wait_ack(timeout_ms=ack_timeout_ms)
    if r is None: raise S2EError("ACK timeout (DATA header)", ERR_TIMEOUT, "data_header_ack")
    if r is False: raise S2EError("NACK (DATA header)", ERR_NACK, "data_header_ack")
    for b in payload: xfer_byte(b)
    r2 = wait_ack(timeout_ms=ack_timeout_ms)
    if r2 is None: raise S2EError("ACK timeout (DATA payload)", ERR_TIMEOUT, "data_payload_ack")
    if r2 is False: raise S2EError("NACK (DATA payload)", ERR_NACK, "data_payload_ack")
    return True

def data_recv(int_timeout_ms: int = DATA_POLL_WAIT_MS,
              rx_timeout_ms: int = RX_TIMEOUT_MS,
              scan_max: int = DATA_SCAN_MAX):
    if not wait_int_low(int_timeout_ms): return None
    if INT_CS_DELAY_US: time.sleep_us(INT_CS_DELAY_US)
    xfer_byte(CMD_B0); xfer_byte(DUMMY); xfer_byte(DUMMY); xfer_byte(DUMMY)
    mv, n, err_code, stage = read_b1_payload_status(timeout_ms=rx_timeout_ms, scan_max=scan_max)
    if err_code != SUCCESS:
        msg = "RX Timeout" if err_code == ERR_TIMEOUT else "RX NACK"
        raise S2EError(msg, err_code, stage)
    return (mv, n)

# -----------------------
# Public APIs Helpers
# -----------------------
def _decode_resp_ascii(mv, n: int) -> str:
    raw = bytes(mv[:n]).split(b"\x00", 1)[0]
    return raw.decode("ascii", "ignore")

def _parse_get_value(cmd: str, resp_ascii: str):
    s = resp_ascii.strip("\r\n")
    cu = cmd.upper()
    return s[len(cu):].strip() if s.upper().startswith(cu) else s.strip()

_NO_PARAM_SET_CMDS = ("SV", "RT", "FR", "EX")

# ----------------------------------------------------------------------
# Public APIs (Optimized return types)
# ----------------------------------------------------------------------

def send_cmd(at_cmd: str, at_param: str):
    """
    Returns tuple: (error_code, value)
    - Success: (SUCCESS, value)  [value is None for SET cmds]
    - Failure: (error_code, None)
    """
    try:
        cmd = (at_cmd or "").strip()
        if not cmd: return (ERR_UNKNOWN, None)

        cmd_u = cmd.upper()
        if cmd_u in ("HELP", "?"):
            print_help()
            return (SUCCESS, None)

        if at_param or (cmd in _NO_PARAM_SET_CMDS):
            cmdline = cmd + (at_param or "")
            at_set(cmdline, ack_timeout_ms=ACK_TIMEOUT_MS)
            return (SUCCESS, None)
        else:
            mv, n = at_get(cmd, int_timeout_ms=INT_TIMEOUT_MS, rx_timeout_ms=RX_TIMEOUT_MS)
            if mv is None or n <= 0:
                return (ERR_UNKNOWN, None)
            resp_ascii = _decode_resp_ascii(mv, n)
            val = _parse_get_value(cmd, resp_ascii)
            return (SUCCESS, val)

    except RuntimeError:
        return (ERR_TIMEOUT, None) # Mapped generic runtime error
    except Exception as e:
        if DEBUG_PRINT: print(f"[CMD ERR] {e}")
        return (ERR_UNKNOWN, None)

def print_info():
    print("=== W55RP20-S2E SPI AT GET/SET test ===")
    print(f"SPI{SPI_ID} baud={SPI_BAUD} POL={POL} PHA={PHA}")
    print(f"CS_HOLD_US={CS_HOLD_US}, CS_GAP_US={CS_GAP_US}, INT_CS_DELAY_US={INT_CS_DELAY_US}")

def send_data(payload):
    """
    Returns integer error code.
    - Success: SUCCESS (0)
    - Failure: Negative integer error code
    """
    try:
        data_send(payload, ack_timeout_ms=ACK_TIMEOUT_MS)
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
    - Success: (memoryview, length) tuple
    - No Data: None
    - Failure: Negative integer error code
    """
    try:
        res = data_recv(
            int_timeout_ms=DATA_POLL_WAIT_MS,
            rx_timeout_ms=RX_TIMEOUT_MS,
            scan_max=DATA_SCAN_MAX,
        )
        if res is None: return None
        return res # (mv, n)

    except S2EError as e:
        if DEBUG_PRINT: print(f"[RX ERR] {e.stage}: {e} (Code: {e.err_code})")
        return e.err_code
    except Exception as e:
        if DEBUG_PRINT: print(f"[RX ERR] System Exception: {e}")
        return ERR_UNKNOWN
