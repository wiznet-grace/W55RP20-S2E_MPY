# 08_mqtt_client.py
# W55RP20-S2E MQTT Client Example
#
# This example demonstrates MQTT Client (OP=5) communication.
# It connects to a broker, subscribes to a topic, and handles 
# incoming messages with Topic/Payload separation.

import time

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
MODE = "uart"   # "spi" or "uart"
USE_DHCP = True 

# MQTT Broker Settings
BROKER_HOST = "192.168.11.2"
BROKER_PORT = "1883"
CLIENT_ID   = "w55rp20_mpy_client"
SUB_TOPIC   = "w55rp20/sub"
PUB_TOPIC   = "w55rp20/pub"
PUB_MESSAGE = "Hello from W55RP20-S2E"
KEEP_ALIVE  = 30  

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
    """Configure the module as MQTT Client via AT commands."""
    ip_mode = "1" if USE_DHCP else "0"
    
    cmds = [
        ("OP", "5"),            # MQTT Client Mode
        ("IM", ip_mode),        # IP Configuration
        ("RH", BROKER_HOST),    # Broker IP
        ("RP", BROKER_PORT),    # Broker Port
        ("PU", PUB_TOPIC),      # Publish Topic
        ("U0", SUB_TOPIC),      # Subscribe Topic
        ("QC", CLIENT_ID),      # Client ID
        ("KA", "1"),            # Keep-Alive Enable
        ("QK", str(KEEP_ALIVE)),# Keep-Alive Interval
        ("PT", "10"),           # Packet transmission time
        ("DG", "2"),            # Debug Level 2 (Includes Topic info)
    ]
    
    if MODE == "uart":
        _enter_at_mode_uart()

    print("[CFG] Applying settings...")
    for c, p in cmds:
        ret = s2e.send_cmd(c, p)
        print(f"  {c}{p} -> {ret}")
        time.sleep_ms(150)

    print("[CFG] Saving & Rebooting...")
    s2e.send_cmd("SV", "")
    time.sleep_ms(200)
    s2e.send_cmd("RT", "")
    
    print(f"[CFG] Waiting {AFTER_RT_WAIT_MS/1000}s for boot...")
    time.sleep_ms(AFTER_RT_WAIT_MS)

def mqtt_communication():
    """Main loop to handle MQTT data stream."""
    print("\n[MQTT] Connected. Listening for data...")
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
                        # Fallback: Print with default topic
                        print(f"[RX] {SUB_TOPIC} : {raw_data}")
            
        except Exception as e:
            print(f"[WARN] Comm Error: {e}. Retrying...")
            time.sleep_ms(100)
            continue
        except KeyboardInterrupt:
            print("\n[STOP] Interrupted by user")
            break

def main():
    if hasattr(s2e, 'print_info'):
        s2e.print_info()
    
    apply_config()
    mqtt_communication()

if __name__ == "__main__":
    main()