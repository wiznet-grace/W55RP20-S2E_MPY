# 06_webserver.py
#
# Web server example (Supports both SPI and UART modes):
# - Configure the module as TCP server + DHCP
# - Listen on local port and serve HTTP responses
# Select mode by changing the MODE variable below.

import time

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
MODE = "spi"   # Set to "spi" or "uart"

# IP Configuration Mode
USE_DHCP = True  # True: DHCP (IM=1), False: Static IP (IM=0)

# Network Configuration
LOCAL_IP    = "192.168.11.100"  # Local IP (Used when USE_DHCP=False)
SUBNET_MASK = "255.255.255.0"   # Subnet Mask (Used when USE_DHCP=False)
GATEWAY     = "192.168.11.1"    # Gateway (Used when USE_DHCP=False)
DNS_SERVER  = "8.8.8.8"         # DNS Server (Used when USE_DHCP=False)

LOCAL_PORT = "80"  # HTTP port to listen on

AFTER_RT_WAIT_MS = 7000

# Timing constants
UART_GUARD_MS = 1000



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
    time.sleep_ms(UART_GUARD_MS)



def apply_config():
    """Configure the module using AT commands."""
    ip_mode = "1" if USE_DHCP else "0"
    
    cmds = [
        ("OP", "1"),            # TCP Server Mode (0:Client, 1:Server)
        ("IM", ip_mode),        # IP Mode (0:Static, 1:DHCP)
        ("LP", LOCAL_PORT),     # Local Port to Listen
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
        ret = s2e.send_cmd("LI", "")
        
        ip_str = None
        if isinstance(ret, tuple):
            err, val = ret
            ip_str = val if err == 0 else None
        else:
            ip_str = ret.get("value") if isinstance(ret, dict) else str(ret)
            
        if ip_str and ip_str != "0.0.0.0":
            print(f"Server IP Assigned: {ip_str}")
            print(f"Port: {LOCAL_PORT}")
            got_ip = True
            break
        
        print(f"  [{i+1}/10] Waiting for IP... (Current: {ip_str})")
        time.sleep(1)

    if not got_ip:
        print("Warning: DHCP failed or timed out. IP is still 0.0.0.0")

    # Exit AT mode to start web server (Data Mode)
    if MODE == "uart":
        print("[CFG] Exiting AT mode (EX) to start web server...")
        _exit_at_mode_uart()

def handle_request():
    """Receive HTTP request and send response."""
    total_bytes = 0
    timeout_ms = 1000
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    
    while time.ticks_diff(time.ticks_ms(), deadline) < 0:
        if MODE == "uart":
            mv, n = s2e.recv_data_mv()
            if mv is not None and n > 0:
                if total_bytes == 0:
                    print("\n[WEB] Client connected")
                chunk = bytes(mv[:n])
                total_bytes += n
                if b'\r\n\r\n' in chunk:
                    break
        else:
            ret = s2e.recv_data()
            if ret is None:
                pass
            elif isinstance(ret, tuple):
                mv, n = ret
                if n > 0:
                    if total_bytes == 0:
                        print("\n[WEB] Client connected")
                    chunk = bytes(mv[:n])
                    total_bytes += n
                    if b'\r\n\r\n' in chunk:
                        break
        
        time.sleep_ms(10)
    
    if total_bytes == 0:
        return False
    
    print(f"[WEB] Received {total_bytes} bytes")
    
    # Build HTTP response
    html_content = "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
    html_content += "<title>W55RP20-S2E Web Server</title>"
    html_content += "</head><body>"
    html_content += "<h1>W55RP20-S2E Web Server</h1>"
    html_content += "<p>Status: Running</p>"
    html_content += f"<p>Mode: {MODE.upper()}</p>"
    html_content += f"<p>Port: {LOCAL_PORT}</p>"
    html_content += "</body></html>"
    
    http_response = (
        "HTTP/1.1 200 OK\r\n"
        "Content-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(html_content)}\r\n"
        "Connection: close\r\n"
        "\r\n"
        f"{html_content}"
    )
    
    # Send HTTP response
    print("[WEB] Sending response...")
    if MODE == "uart":
        s2e.send_data(http_response)
    else:
        err = s2e.send_data(http_response)
        if err != 0:
            print(f"[ERR] Failed to send response: {err}")
            return True
    
    print(f"[WEB] Sent {len(http_response)} bytes")
    
    # Wait for client to receive all data before connection closes
    time.sleep_ms(500)
    return True

def main():
    s2e.print_info()
    apply_config()
    
    print("[WEB] Web server started. Listening for requests...")
    
    while True:
        handle_request()
        time.sleep_ms(100)

if __name__ == "__main__":
    main()
