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
MODE = "spi"   # Set to "spi" or "uart"

REMOTE_IP   = "192.168.11.2"
REMOTE_PORT = "5000"

# Printing flags
PRINT_INFO = True
PRINT_HELP = False

# Timing constants
UART_GUARD_MS = 600
UART_AFTER_RT_WAIT_MS = 7000

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
    UART typically just waits for a fixed duration after reboot.
    """
    deadline = time.ticks_add(time.ticks_ms(), max_ms)

    while time.ticks_diff(time.ticks_ms(), deadline) < 0:
        r = s2e.send_cmd("ST", "")
        
        # Extract value from response dict
        v = None
        if isinstance(r, dict):
            v = r.get("value")
            if v is None: 
                v = r.get("raw")

        # Uncomment to debug status polling
        # print("[ST]", r)

        if v and ("CONNECT" in str(v).upper()):
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
        r = s2e.send_cmd(c, p)
        print(f"  Set {c}{p} -> {r}")
        time.sleep_ms(100)

    # Save Settings
    print("[CFG] Saving (SV)...")
    print(" ", s2e.send_cmd("SV", ""))
    time.sleep_ms(200)

    # Reboot Module
    print("[CFG] Rebooting (RT)...")
    print(" ", s2e.send_cmd("RT", ""))

    # Post-reboot wait
    if MODE == "uart":
        # UART needs a long wait for boot + IP acquisition + Connection
        print(f"[CFG] Waiting {UART_AFTER_RT_WAIT_MS/1000}s for UART boot/connect...")
        time.sleep_ms(UART_AFTER_RT_WAIT_MS)
    else:
        # SPI polls status later, so just a short boot delay is enough
        print("[CFG] Waiting 2.0s for SPI boot...")
        time.sleep_ms(2000)

def loopback():
    """Main data loopback routine."""
    print(f"[LOOP] Start TCP client loopback ({MODE.upper()} DATA)")

    rx_cnt = 0
    tx_cnt = 0
    miss_cnt = 0
    last_log = time.ticks_ms()
    
    # [Config] GC execution interval when idle (Unit: loop iterations)
    # Since the loop sleeps for 2ms, 1000 iterations equal approx. 2 seconds.
    IDLE_GC_THRESHOLD = 1000 
    idle_counter = 0

    while True:
        data_received = False
        
        if MODE == "uart":
            # --------------------------------------------------
            # UART Mode Loop
            # --------------------------------------------------
            mv, n = s2e.recv_data_mv()
            if mv is not None and n > 0:
                s2e.send_data(mv, n)
                rx_cnt += 1
                tx_cnt += 1
                data_received = True
            else:
                miss_cnt += 1

        else:
            # --------------------------------------------------
            # SPI Mode Loop
            # --------------------------------------------------
            rx = s2e.recv_data()
            
            # Check if reception was successful
            if rx.get("ok"):
                mv = rx.get("mv")
                n = int(rx.get("len", 0))
                
                if mv is not None and n > 0:
                    # Echo back the data
                    tx = s2e.send_data(mv[:n])
                    
                    if tx.get("ok"):
                        rx_cnt += 1
                        tx_cnt += 1
                        data_received = True
            else:
                if rx.get("err_code") is None:
                    miss_cnt += 1

        # --------------------------------------------------
        # [Core] Smart Garbage Collection
        # Counts only when idle (no data) and cleans up occasionally.
        # GC never runs during data transmission, preventing latency spikes.
        # --------------------------------------------------
        if data_received:
            idle_counter = 0  # Reset counter when data is received (Focus on communication!)
        else:
            idle_counter += 1
            if idle_counter > IDLE_GC_THRESHOLD:
                # No data for approx. 2 seconds -> Time to clean up!
                gc.collect()
                idle_counter = 0
                # print("[GC] Memory cleaned during idle time")

        # --------------------------------------------------
        # Common Status Logging
        # --------------------------------------------------
        # Log once per second
        now = time.ticks_ms()
        if time.ticks_diff(now, last_log) >= 1000:
            # print(f"[STAT] rx={rx_cnt}, tx={tx_cnt}, misses={miss_cnt}")
            last_log = now
            miss_cnt = 0

        # Yield CPU
        time.sleep_ms(2)

def main():
    if PRINT_INFO:
        s2e.print_info()
    if PRINT_HELP:
        s2e.print_help()

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
