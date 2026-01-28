# 03_tcp_server_loopback.py
#
# TCP Server loopback example (Supports both SPI and UART modes):
# - Configure the module as TCP Server + DHCP
# - Local Port: 5000
# - Waits for a client to connect, then echoes back received data.
#
# Select mode by changing the MODE variable below.

import time
import gc  # Required for manual memory management

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
MODE = "spi"   # Set to "spi" or "uart"

LOCAL_PORT = "5000"  # Port to listen on

# Printing flags
PRINT_INFO = True
PRINT_HELP = False

# Timing constants
UART_GUARD_MS = 600
UART_AFTER_RT_WAIT_MS = 7000

# SPI specific constants
SPI_CONNECT_TIMEOUT_MS = 60000  # Server might wait longer for a client
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

def _wait_for_client_spi(max_ms=SPI_CONNECT_TIMEOUT_MS):
    """
    SPI Only: Poll ST command until a Client connects ('CONNECT' status).
    """
    print(f"[SRV] Waiting for client connection on port {LOCAL_PORT}...")
    deadline = time.ticks_add(time.ticks_ms(), max_ms)

    while time.ticks_diff(time.ticks_ms(), deadline) < 0:
        ret = s2e.send_cmd("ST", "")
        
        # Extract value based on return type (tuple vs dict)
        val = None
        if isinstance(ret, tuple): # SPI Driver (new)
            err, val = ret
            if err != 0: val = None
        elif isinstance(ret, dict): # UART Driver (legacy dict)
            val = ret.get("value")

        # Uncomment to debug status polling
        # if val: print(f"[ST] {val}")

        if val and ("CONNECT" in str(val).upper()):
            print("[ST] Client CONNECTED!")
            return True

        time.sleep_ms(SPI_ST_POLL_MS)

    print("[ST] Timeout: No client connected.")
    return False

def apply_config():
    """Configure the module using AT commands."""
    cmds = [
        ("OP", "1"),            # TCP Server Mode (0:Client, 1:Server)
        ("IM", "1"),            # DHCP Mode
        ("LP", LOCAL_PORT),     # Local Port to Listen
        ("DG", "1"),            # Debug Message Enable
    ]

    # For UART, we must explicitly enter AT mode first
    if MODE == "uart":
        print("[CFG] Entering AT mode (UART)...")
        _enter_at_mode_uart()

    print("[CFG] Applying settings...")
    for c, p in cmds:
        ret = s2e.send_cmd(c, p)
        
        # Log result
        res_str = f"{ret}"
        if isinstance(ret, tuple):
            err, _ = ret
            res_str = "OK" if err == 0 else f"ERR({err})"
        
        print(f"  Set {c}{p} -> {res_str}")
        time.sleep_ms(100)

    # Save Settings
    print("[CFG] Saving (SV)...")
    s2e.send_cmd("SV", "") #
    time.sleep_ms(200)

    # Reboot Module
    print("[CFG] Rebooting (RT)...")
    s2e.send_cmd("RT", "") #

    # Post-reboot wait
    if MODE == "uart":
        print(f"[CFG] Waiting {UART_AFTER_RT_WAIT_MS/1000}s for UART boot...")
        time.sleep_ms(UART_AFTER_RT_WAIT_MS)
    else:
        print("[CFG] Waiting 2.0s for SPI boot...")
        time.sleep_ms(5000)

    # [Server Feature] Check Assigned IP
    print("[CFG] Checking Assigned IP...")
    ret = s2e.send_cmd("LI", "")  # LI: Local IP
    
    ip_str = None
    if isinstance(ret, tuple): # SPI
        err, val = ret
        if err == 0: ip_str = val
    elif isinstance(ret, dict): # UART
        ip_str = ret.get("value")
        
    if ip_str:
        print(f"  Server IP: {ip_str}")
        print(f"  Port: {LOCAL_PORT}")
    else:
        print("  Failed to get IP address")

def loopback():
    """Main data loopback routine."""
    print(f"[LOOP] Start TCP Server loopback ({MODE.upper()} DATA)")

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
            # UART Mode Loop
            # --------------------------------------------------
            # Use recv_data_mv for zero-copy if available
            try:
                mv, n = s2e.recv_data_mv() #
                if mv is not None and n > 0:
                    # Echo back using length argument to avoid slicing copy
                    s2e.send_data(mv, length=n) 
                    rx_cnt += 1
                    tx_cnt += 1
                    data_received = True
                else:
                    miss_cnt += 1
            except AttributeError:
                pass 

        else:
            # --------------------------------------------------
            # SPI Mode Loop
            # --------------------------------------------------
            ret = s2e.recv_data() #
            
            # Case 1: Success Tuple (mv, n)
            if isinstance(ret, tuple):
                mv, n = ret
                if n > 0:
                    # Echo back
                    err = s2e.send_data(mv[:n])
                    if err == 0: # SUCCESS
                        rx_cnt += 1
                        tx_cnt += 1
                        data_received = True
            
            # Case 2: Error Code (int)
            elif isinstance(ret, int):
                # ret < 0 means error
                miss_cnt += 1
                
            # Case 3: None (No Data) -> Do nothing

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
            # print(f"[STAT] rx={rx_cnt}, tx={tx_cnt}")
            last_log = now
            miss_cnt = 0

        # Yield CPU
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
        if not _wait_for_client_spi():
            print("[ERR] No client connected within timeout.")
            return

    # 3. Start Loopback
    loopback()

if __name__ == "__main__":
    main()