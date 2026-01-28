# 02_tcp_client_loopback.py
#
# TCP client loopback example (Supports both SPI and UART modes):
# - Configure the module as TCP client + DHCP
# Select mode by changing the MODE variable below.

import time
import gc  # Required for manual memory management

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
MODE = "uart"   # Set to "spi" or "uart"

REMOTE_IP   = "192.168.11.2"
REMOTE_PORT = "5000"

# Printing flags
PRINT_INFO = True
PRINT_HELP = False

AFTER_RT_WAIT_MS = 5000

# Timing constants
UART_GUARD_MS = 600

# SPI specific constants
SPI_CONNECT_TIMEOUT_MS = 20000
SPI_ST_POLL_MS = 500

# -------------------------------------------------------------------------
# Driver Import
# -------------------------------------------------------------------------
if MODE == "spi":
    import w55rp20_s2e_spi as s2e
elif MODE == "uart":
    import w55rp20_s2e_uart as s2e
else:
    raise ValueError("MODE must be 'spi' or 'uart'")

# -------------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------------
def _enter_at_mode_uart():
    """Enter AT command mode for UART (Guard time + '+++' + Guard time)."""
    time.sleep_ms(UART_GUARD_MS)
    s2e.send_data("+++")
    time.sleep_ms(UART_GUARD_MS)

def _wait_connected_spi(max_ms=SPI_CONNECT_TIMEOUT_MS):
    """
    SPI Only: Poll ST command until 'CONNECT' status is reported.
    Uses new (err, val) return structure.
    """
    deadline = time.ticks_add(time.ticks_ms(), max_ms)

    while time.ticks_diff(time.ticks_ms(), deadline) < 0:
        # AT Command returns (err, val) tuple
        ret = s2e.send_cmd("ST", "")
        
        val = None
        if isinstance(ret, tuple):
            err, val = ret
            # Check success (0)
            if err != 0: val = None
        elif isinstance(ret, dict): # Fallback for old/UART driver
            val = ret.get("value")

        if val and ("CONNECT" in str(val).upper()):
            print("[ST] CONNECTED!")
            return True

        time.sleep_ms(SPI_ST_POLL_MS)

    print("[ST] Timeout waiting for connection.")
    return False

def apply_config():
    """Configure the module using AT commands."""
    cmds = [
        ("OP", "0"),            # TCP Client Mode
        ("IM", "1"),            # DHCP Mode
        ("RH", REMOTE_IP),      # Remote Host IP
        ("RP", REMOTE_PORT),    # Remote Port
        ("DG", "1"),            # Debug Message Enable
    ]

    # For UART, we must explicitly enter AT mode first
    if MODE == "uart":
        print("[CFG] Entering AT mode (UART)...")
        _enter_at_mode_uart()

    print("[CFG] Applying settings...")
    for c, p in cmds:
        ret = s2e.send_cmd(c, p)
        
        # Format output based on return type
        if isinstance(ret, tuple):
            err, val = ret
            res_str = f"OK" if err == 0 else f"ERR({err})"
            print(f"  Set {c}{p} -> {res_str}")
        else:
            print(f"  Set {c}{p} -> {ret}")
            
        time.sleep_ms(100)

    # Save Settings
    print("[CFG] Saving (SV)...")
    s2e.send_cmd("SV", "")
    time.sleep_ms(200)

    # Reboot Module
    print("[CFG] Rebooting (RT)...")
    s2e.send_cmd("RT", "")

    # Post-reboot wait
    if MODE == "uart":
        print(f"[CFG] Waiting {AFTER_RT_WAIT_MS/1000}s for UART boot/connect...")
        time.sleep_ms(AFTER_RT_WAIT_MS)
    else:
        print(f"[CFG] Waiting {AFTER_RT_WAIT_MS/1000}s for SPI boot/connect...")
        time.sleep_ms(AFTER_RT_WAIT_MS)

def loopback():
    """Main data loopback routine."""
    print(f"[LOOP] Start TCP client loopback ({MODE.upper()} DATA)")

    rx_cnt = 0
    tx_cnt = 0
    miss_cnt = 0
    last_log = time.ticks_ms()
    
    # [Config] GC execution interval when idle
    IDLE_GC_THRESHOLD = 5000 
    idle_counter = 0

    while True:
        data_received = False
        
        if MODE == "uart":
            # --------------------------------------------------
            # UART Mode Loop (Assumes UART driver still uses old API or is updated)
            # --------------------------------------------------
            # If UART driver is NOT updated, this might need adjustment.
            # Assuming s2e.recv_data_mv() exists for UART as per original code.
            try:
                mv, n = s2e.recv_data_mv() # UART usually provides this method
                if mv is not None and n > 0:
                    s2e.send_data(mv, n)
                    rx_cnt += 1
                    tx_cnt += 1
                    data_received = True
                else:
                    miss_cnt += 1
            except AttributeError:
                # Fallback if UART driver uses recv_data
                pass 

        else:
            # --------------------------------------------------
            # SPI Mode Loop (Zero-Copy)
            # --------------------------------------------------
            # recv_data returns (mv, n) or None or ErrorCode(int)
            ret = s2e.recv_data()
            
            if isinstance(ret, tuple):
                mv, n = ret
                if n > 0:
                    # Echo back. send_data returns 0 on Success.
                    err = s2e.send_data(mv[:n])
                    
                    if err == 0: # SUCCESS
                        rx_cnt += 1
                        tx_cnt += 1
                        data_received = True
            elif isinstance(ret, int):
                # Error code returned
                miss_cnt += 1
            # If ret is None (No Data), do nothing

        # --------------------------------------------------
        # [Core] Smart Garbage Collection
        # --------------------------------------------------
        if data_received:
            idle_counter = 0
        else:
            idle_counter += 1
            if idle_counter > IDLE_GC_THRESHOLD:
                gc.collect()
                idle_counter = 0

        # --------------------------------------------------
        # Common Status Logging
        # --------------------------------------------------
        now = time.ticks_ms()
        if time.ticks_diff(now, last_log) >= 1000:
            # print(f"[STAT] rx={rx_cnt}, tx={tx_cnt}, misses={miss_cnt}")
            last_log = now
            miss_cnt = 0

        # No sleep needed for SPI (driver has poll wait)
        if MODE == "uart":
            time.sleep_ms(2)

def main():
    if PRINT_INFO:
        try: s2e.print_info()
        except: pass
    if PRINT_HELP:
        try: s2e.print_help()
        except: pass

    # 1. Setup
    apply_config()

    # 2. Wait for Connection (SPI only)
    if MODE == "spi":
        if not _wait_connected_spi():
            print("[ERR] Connection timed out (SPI)")
            return

    # 3. Start Loopback
    loopback()

if __name__ == "__main__":
    main()
