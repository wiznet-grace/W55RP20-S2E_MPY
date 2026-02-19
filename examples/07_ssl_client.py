# 07_ssl_client.py
#
# SSL/TLS TCP Client Example
# - Supports both SPI and UART communication modes
# - Configure W55RP20-S2E module as SSL TCP client (OP=4)
# - Connect to SSL server and send initial message
# - Continuously receive and display server responses

import time

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
MODE = "spi"   # Set to "spi" or "uart"

# IP Configuration Mode
USE_DHCP = True  # True: DHCP (IM=1), False: Static IP (IM=0)

# Network Configuration
LOCAL_IP    = "192.168.11.123"  # Local IP (Used when USE_DHCP=False)
SUBNET_MASK = "255.255.255.0"   # Subnet Mask (Used when USE_DHCP=False)
GATEWAY     = "192.168.11.1"    # Gateway (Used when USE_DHCP=False)
DNS_SERVER  = "168.126.63.1"    # DNS Server (Used when USE_DHCP=False)

# Remote Server Configuration
REMOTE_HOST = "192.168.11.2"    # Server hostname or IP
REMOTE_PORT = "8443"            # Server port

AFTER_RT_WAIT_MS = 20000        # Wait time after reboot for SSL handshake (20s)

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
    """Configure the module as SSL TCP client."""
    ip_mode = "1" if USE_DHCP else "0"
    
    cmds = [
        ("OP", "4"),            # SSL TCP Client Mode
        ("IM", ip_mode),        # IP Mode (0:Static, 1:DHCP)
        ("RH", REMOTE_HOST),    # Remote Host
        ("RP", REMOTE_PORT),    # Remote Port
        ("RC", "0"),            # Root CA verify
        ("CE", "0"),            # Client certificate
        ("SO", "30000"),        # Socket timeout
        ("PT", "10"),           # Packet transmission time
        ("DG", "2"),            # Debug messages
    ]
    
    if not USE_DHCP:
        cmds.extend([
            ("LI", LOCAL_IP), ("SM", SUBNET_MASK), ("GW", GATEWAY), ("DS", DNS_SERVER),
        ])

    if MODE == "uart":
        _enter_at_mode_uart()

    print("[CFG] Configuring...")
    for c, p in cmds:
        ret = s2e.send_cmd(c, p)
        if isinstance(ret, tuple):
            err, val = ret
            status = "OK" if err == 0 else f"ERR({err})"
        else:
            status = ret
        print(f"  {c}{p} -> {status}")
        time.sleep_ms(100)

    print("[CFG] Saving...")
    s2e.send_cmd("SV", "")
    time.sleep_ms(500)
    
    print("[CFG] Rebooting...")
    s2e.send_cmd("RT", "")
    
def ssl_communication():
    """Continuously receive data and send it back (loopback)."""
    print("\n[SSL] Connecting...")
    first_data = True
    
    try:
        while True:
            try:
                if MODE == "spi":
                    ret = s2e.data_recv(int_timeout_ms=50, rx_timeout_ms=200, scan_max=100)
                else:
                    ret = s2e.recv_data()
                
                if isinstance(ret, tuple):
                    mv, n = ret
                    if n > 0:
                        if first_data:
                            print("[SSL] Connected!\n")
                            first_data = False
                        
                        data = bytes(mv[:n])
                        # Display received data
                        try:
                            print(data.decode('utf-8', 'ignore'), end='')
                        except:
                            print(data)
                        # Send back (loopback)
                        s2e.send_data(data)
                else:
                    time.sleep_ms(10)
            except:
                time.sleep_ms(10)
    
    except KeyboardInterrupt:
        print(f"\n[DONE] Stopped")
    
def main():
    """Main function."""
    if hasattr(s2e, 'print_info'):
        s2e.print_info()
    
    apply_config()
    ssl_communication()

if __name__ == "__main__":
    main()