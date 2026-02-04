# 05_http_client.py
#
# HTTP client example (Supports both SPI and UART modes):
# - Configure the module as TCP client + DHCP
# - Connect to httpbin.org and send HTTP GET requests
# Select mode by changing the MODE variable below.

import time

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
MODE = "uart"   # Set to "spi" or "uart"

# IP Configuration Mode
USE_DHCP = True  # True: DHCP (IM=1), False: Static IP (IM=0)

# Network Configuration
LOCAL_IP    = "192.168.11.100"  # Local IP (Used when USE_DHCP=False)
SUBNET_MASK = "255.255.255.0"   # Subnet Mask (Used when USE_DHCP=False)
GATEWAY     = "192.168.11.1"    # Gateway (Used when USE_DHCP=False)
DNS_SERVER  = "8.8.8.8"         # DNS Server (Used when USE_DHCP=False)
REMOTE_IP   = "httpbin.org"  # HTTP server (domain or IP)
REMOTE_PORT = "80"           # HTTP port

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

def _wait_connected_spi(max_ms=SPI_CONNECT_TIMEOUT_MS, show_waiting=False):
    """
    SPI Only: Poll ST command until 'CONNECT' status is reported.
    Uses new (err, val) return structure.
    """
    if show_waiting:
        print(f"[ST] Waiting for server connection (timeout: {max_ms/1000}s)...")
    
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
    ip_mode = "1" if USE_DHCP else "0"
    
    cmds = [
        ("OP", "0"),            # TCP Client Mode
        ("IM", ip_mode),        # IP Mode (0:Static, 1:DHCP)
        ("RH", REMOTE_IP),      # Remote Host IP
        ("RP", REMOTE_PORT),    # Remote Port
        ("DG", "1"),            # Debug Message Enable
    ]
    
    # Add Static IP settings if not using DHCP
    if not USE_DHCP:
        cmds.extend([
            ("LI", LOCAL_IP),
            ("SM", SUBNET_MASK),
            ("GW", GATEWAY),
            ("DS", DNS_SERVER),
        ])

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

def http_request():
    """Send HTTP GET request and receive response."""
    print(f"[HTTP] Sending GET request to {REMOTE_IP}...")
    
    # Build HTTP GET request
    http_req = (
        f"GET /get HTTP/1.1\r\n"
        f"Host: {REMOTE_IP}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    
    # Send HTTP request
    print("[HTTP] Sending request...")
    if MODE == "uart":
        s2e.send_data(http_req)
    else:
        err = s2e.send_data(http_req)
        if err != 0:
            print(f"[ERR] Failed to send request: {err}")
            return
    
    print("[HTTP] Request sent. Receiving response...")
    
    # Receive and display HTTP response in real-time
    total_bytes = 0
    timeout_ms = 10000
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    no_data_count = 0
    max_no_data = 200  # 200 attempts without data (2 seconds at 10ms interval)
    
    while time.ticks_diff(time.ticks_ms(), deadline) < 0:
        data_received = False
        
        if MODE == "uart":
            mv, n = s2e.recv_data_mv()
            if mv is not None and n > 0:
                if total_bytes == 0:
                    print("[RX]")
                chunk = bytes(mv[:n])
                total_bytes += n
                # Print immediately
                try:
                    print(chunk.decode('utf-8'), end='')
                except:
                    print(chunk, end='')
                data_received = True
                no_data_count = 0
        else:
            try:
                mv, n = s2e.recv_data()
                if n > 0:
                    if total_bytes == 0:
                        print("[RX]")
                    chunk = bytes(mv[:n])
                    total_bytes += n
                    # Print immediately
                    try:
                        print(chunk.decode('utf-8'), end='')
                    except:
                        print(chunk, end='')
                    data_received = True
                    no_data_count = 0
            except (TypeError, ValueError):
                pass
        
        if not data_received:
            no_data_count += 1
            if no_data_count >= max_no_data:
                break
        
        time.sleep_ms(10)  # Poll interval
    
    print(f"\n[HTTP] Received {total_bytes} bytes")

def main():
    s2e.print_info()
    # s2e.print_help()

    # 1. Setup
    apply_config()

    # 2. Wait for Connection (SPI only - UART waits in apply_config)
    if MODE == "spi":
        if not _wait_connected_spi():
            print("[ERR] Connection timed out (SPI)")
            return
    else:
        # UART: Additional wait for TCP connection to be fully established
        print("[UART] Waiting for connection...")
        time.sleep_ms(3000)

    # 3. Send HTTP Request and receive response (with timeout)
    http_request()
    
if __name__ == "__main__":
    main()
