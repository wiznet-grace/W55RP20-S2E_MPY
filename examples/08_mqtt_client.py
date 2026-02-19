# 08_mqtt_client.py
#
# MQTT Client example (Supports both SPI and UART modes):
# - Configure the module as MQTT client (OP=5) + DHCP
# - Connect to broker, subscribe to topic, and handle incoming messages
#
# Select mode by changing the MODE variable below.

import time

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
MODE     = "uart"  # Set to "spi" or "uart"
USE_DHCP = True    # True: DHCP (IM=1), False: Static IP (IM=0)

# MQTT Broker Settings
BROKER_HOST = "192.168.11.2"
BROKER_PORT = "1883"
CLIENT_ID   = "w55rp20_mpy_client"
SUB_TOPIC   = "w55rp20/sub"
PUB_TOPIC   = "w55rp20/pub"
PUB_MESSAGE = "Hello from W55RP20-S2E"
KEEP_ALIVE  = 30

# Network Configuration
LOCAL_IP    = "192.168.11.100"  # Local IP (Used when USE_DHCP=False)
SUBNET_MASK = "255.255.255.0"   # Subnet Mask (Used when USE_DHCP=False)
GATEWAY     = "192.168.11.1"    # Gateway (Used when USE_DHCP=False)
DNS_SERVER  = "8.8.8.8"         # DNS Server (Used when USE_DHCP=False)

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
        ("OP", "5"),            # MQTT Client Mode
        ("IM", ip_mode),        # IP Mode (0:Static, 1:DHCP)
        ("RH", BROKER_HOST),    # Remote Host (Broker IP)
        ("RP", BROKER_PORT),    # Remote Port
        ("PU", PUB_TOPIC),      # MQTT Publish Topic
        ("U0", SUB_TOPIC),      # MQTT Subscribe Topic
        ("QC", CLIENT_ID),      # MQTT Client ID
        ("KA", "1"),            # Keep-Alive Enable
        ("QK", str(KEEP_ALIVE)),# Keep-Alive Interval
        ("PT", "10"),           # Packet Transmission Time
        ("DG", "2"),            # Debug Message Enable (Includes Topic info)
    ]

    # Add Static IP settings if not using DHCP
    if not USE_DHCP:
        cmds.extend([
            ("LI", LOCAL_IP),
            ("SM", SUBNET_MASK),
            ("GW", GATEWAY),
            ("DS", DNS_SERVER),
        ])

    if MODE == "uart":
        print("[CFG] Entering AT mode (UART)...")
        _enter_at_mode_uart()

    print("[CFG] Applying settings...")
    for c, p in cmds:
        ret = s2e.send_cmd(c, p)
        if isinstance(ret, tuple):
            err, val = ret
            res_str = "OK" if err == 0 else f"ERR({err})"
            print(f"  Set {c}{p} -> {res_str}")
        else:
            print(f"  Set {c}{p} -> {ret}")
        time.sleep_ms(150)

    # Save Settings
    print("[CFG] Saving (SV)...")
    s2e.send_cmd("SV", "")
    time.sleep_ms(200)

    # Reboot Module
    print("[CFG] Rebooting (RT)...")
    s2e.send_cmd("RT", "")

    print(f"[CFG] Waiting {AFTER_RT_WAIT_MS/1000}s for boot...")
    time.sleep_ms(AFTER_RT_WAIT_MS)

def mqtt_communication():
    """Main loop to handle MQTT data stream."""
    print(f"\n[MQTT] Start MQTT client ({MODE.upper()} DATA)")
    time.sleep_ms(500)

    # Send initial message
    s2e.send_data(PUB_MESSAGE)

    while True:
        try:
            # 1. Receive Data
            if MODE == "spi":
                res = s2e.recv_data()
            else:
                res = s2e.recv_data_mv()

            # 2. Process Data
            if isinstance(res, tuple):
                mv, n = res
                if n > 0:
                    raw_data = bytes(mv[:n]).decode('utf-8', 'ignore').strip()

                    # Check for 'Topic : Payload' format (DG=2 feature)
                    if " : " in raw_data:
                        print(f"[RX] {raw_data}")
                    else:
                        # Fallback: print with default subscribe topic
                        print(f"[RX] {SUB_TOPIC} : {raw_data}")

        except Exception as e:
            print(f"[WARN] Comm Error: {e}. Retrying...")
            time.sleep_ms(100)
            continue
        except KeyboardInterrupt:
            print("\n[STOP] Interrupted by user")
            break

def main():
    s2e.print_info()
    # s2e.print_help()

    # 1. Setup
    apply_config()

    # 2. Start MQTT communication
    mqtt_communication()

if __name__ == "__main__":
    main()

