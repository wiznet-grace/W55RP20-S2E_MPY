# 04_udp_loopback.py
#
# UDP Loopback example (Supports both SPI and UART modes):
# - Configure the module as UDP Mode (OP=3) + DHCP
# - Local Port: 5000 (Listening)
# - Remote Host/Port: Destination for echoed data (Must match PC's IP)
#
# Select mode by changing the MODE variable below.

import time
import gc  # Required for manual memory management

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
MODE = "spi"   # Set to "spi" or "uart"

# [UDP Configuration]
# UDP is connectionless. You MUST specify the destination IP (Your PC).
LOCAL_PORT  = "5000"          # Port to listen on (Pico)
REMOTE_IP   = "192.168.11.2"  # Destination IP (PC's IP) - CHANGE THIS!
REMOTE_PORT = "5000"          # Destination Port (PC's Port)

# Printing flags
PRINT_INFO = True
PRINT_HELP = False

# Timing constants
UART_GUARD_MS = 1000
AFTER_RT_WAIT_MS = 5000

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

def _exit_at_mode_uart():
    """Exit AT command mode for UART (Send 'EX')."""
    s2e.send_cmd("EX", "")
    time.sleep_ms(200)

def apply_config():
    """Configure the module using AT commands."""
    cmds = [
        ("OP", "3"),            # UDP Mode (3: UDP)
        ("IM", "1"),            # DHCP Mode
        ("LP", LOCAL_PORT),     # Local Port (Listening)
        ("RH", REMOTE_IP),      # Remote Host IP (Destination)
        ("RP", REMOTE_PORT),    # Remote Port (Destination)
        ("DG", "1"),            # Debug Message Enable
    ]

    # UART Specific Settings: Apply Packet Time (PT)
    # For UART, we must explicitly enter AT mode first
    if MODE == "uart":
        cmds.append(("PT", "10")) # Packet Time: 10ms
        print("[CFG] Entering AT mode (UART)...")
        _enter_at_mode_uart()

    print("[CFG] Applying UDP settings...")
    for c, p in cmds:
        # Tuple return handling (err, val)
        ret = s2e.send_cmd(c, p)
        res_str = f"{ret}"
        if isinstance(ret, tuple):
            err, val = ret
            res_str = "OK" if err == 0 else f"ERR({err})"
        
        print(f"  Set {c}{p} -> {res_str}")
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
        print(f"[CFG] Waiting {AFTER_RT_WAIT_MS/1000}s for UART boot...")
        time.sleep_ms(AFTER_RT_WAIT_MS)
        
        # The module returns to Data Mode after reboot.
        # We must re-enter AT mode to query the IP address.
        print("[CFG] Re-entering AT mode to check IP...")
        _enter_at_mode_uart()
    else:
        print(f"[CFG] Waiting {AFTER_RT_WAIT_MS/1000}s for SPI boot...")
        time.sleep_ms(AFTER_RT_WAIT_MS)

    # Check Assigned IP (DHCP)
    print("[CFG] Checking Assigned IP (max 10s)...")
    
    got_ip = False
    for i in range(10):
        ret = s2e.send_cmd("LI", "")  # LI: Local IP
        
        ip_str = None
        if isinstance(ret, tuple):
            err, val = ret
            if err == 0: ip_str = val
        elif isinstance(ret, dict):
             ip_str = ret.get("value")

        if ip_str and ip_str != "0.0.0.0":
            print(f"Server IP Assigned: {ip_str}")
            print(f"Listening Port: {LOCAL_PORT}")
            print(f"Target PC: {REMOTE_IP}:{REMOTE_PORT}")
            got_ip = True
            break
        
        print(f"  [{i+1}/10] Waiting for IP... (Current: {ip_str})")
        time.sleep(1)

    if not got_ip:
        print("Warning: DHCP failed or timed out. IP is still 0.0.0.0")

    # Exit AT mode to start data loopback (Data Mode)
    if MODE == "uart":
        print("[CFG] Exiting AT mode (EX) to start data loopback...")
        _exit_at_mode_uart()

def loopback():
    """Main data loopback routine."""
    print(f"[LOOP] Start UDP loopback ({MODE.upper()} DATA)")

    rx_cnt = 0
    tx_cnt = 0
    miss_cnt = 0
    last_log = time.ticks_ms()
    
    # [Config] GC execution interval when idle
    # Since the loop sleeps for 2ms, 1000 iterations equal approx. 2 seconds.
    IDLE_GC_THRESHOLD = 1000 
    idle_counter = 0

    while True:
        data_received = False
        
        if MODE == "uart":
            # --------------------------------------------------
            # UART Mode Loop
            # --------------------------------------------------
            # Use recv_data_mv for zero-copy
            mv, n = s2e.recv_data_mv()
            if mv is not None and n > 0:
                # Echo back using length argument to avoid slicing copy
                s2e.send_data(mv, length=n) 
                rx_cnt += 1
                tx_cnt += 1
                data_received = True
            else:
                miss_cnt += 1

        else:
            # --------------------------------------------------
            # SPI Mode Loop
            # --------------------------------------------------
            ret = s2e.recv_data()
            
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
        # Counts only when idle (no data) and cleans up occasionally.
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
            # print(f"[STAT] rx={rx_cnt}, tx={tx_cnt}, miss={miss_cnt}")
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
    
    # 2. Start Loopback (UDP is connectionless, no waiting)
    loopback()

if __name__ == "__main__":
    main()