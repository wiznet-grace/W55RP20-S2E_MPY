# 09_mqtts_client.py
#
# MQTTS (AWS IoT Core) example (Supports both SPI and UART modes):
# - Configure the module as MQTTS client (OP=6) + DHCP
# - Upload Root CA / Client Certificate / Private Key via AT commands
# - Publish initial message and receive subscribed topic data
#
# Select mode by changing the MODE variable below.

import time

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
MODE     = "spi"  # Set to "spi" or "uart"
USE_DHCP = True    # True: DHCP (IM=1), False: Static IP (IM=0)

# AWS IoT Settings
BROKER_HOST = "YOUR_AWS_ENDPOINT"
BROKER_PORT = "8883"
CLIENT_ID   = "w55rp20_aws_client"
SUB_TOPIC   = "sdk/test/python"
PUB_TOPIC   = "sdk/test/python1"
PUB_MESSAGE = "Hello from W55RP20-S2E to AWS IoT"
KEEP_ALIVE  = 60

# Network Configuration
LOCAL_IP    = "192.168.11.100"  # Local IP (Used when USE_DHCP=False)
SUBNET_MASK = "255.255.255.0"   # Subnet Mask (Used when USE_DHCP=False)
GATEWAY     = "192.168.11.1"    # Gateway (Used when USE_DHCP=False)
DNS_SERVER  = "8.8.8.8"         # DNS Server (Used when USE_DHCP=False)

# Timing constants
UART_GUARD_MS    = 1000
AFTER_RT_WAIT_MS = 15000  # Longer wait required for TLS handshake
PACKET_WAIT_MS   = 50     # Accumulate RX chunks until idle for this duration (ms)

# -------------------------------------------------------------------------
# AWS Certificates
# -------------------------------------------------------------------------
AWS_CA_CERT = (
    "-----BEGIN CERTIFICATE-----\r\n"
    "MIIDQTCCAimgAwIBAgITBmyfz5m/jAo54vB4ikPmljZbyjANBgkqhkiG9w0BAQsF\r\n"
    "... (Root CA contents) ...\r\n"
    "-----END CERTIFICATE-----\r\n"
)

AWS_CLIENT_CERT = (
    "-----BEGIN CERTIFICATE-----\r\n"
    "MIIDWTCCAkGgAwIBAgIQPcnRE...\r\n"
    "... (Client Cert contents) ...\r\n"
    "-----END CERTIFICATE-----\r\n"
)

AWS_PRIVATE_KEY = (
    "-----BEGIN RSA PRIVATE KEY-----\r\n"
    "MIIEpAIBAAKCAQEA...\r\n"
    "... (Private Key contents) ...\r\n"
    "-----END RSA PRIVATE KEY-----\r\n"
)

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

def upload_certs():
    """Upload Root CA, Client Certificate, and Private Key via OC / LC / PK commands."""
    cert_actions = [
        ("OC", AWS_CA_CERT),     # Root CA
        ("LC", AWS_CLIENT_CERT), # Client Cert
        ("PK", AWS_PRIVATE_KEY)  # Private Key
    ]

    print("[CERT] Starting certificate upload...")

    for cmd, content in cert_actions:
        print(f"  Uploading {cmd} ({len(content)} bytes)...")
        ret = s2e.send_cmd(cmd, content)
        print(f"  Result: {ret}")

        # Wait for module to write certificate data to flash
        time.sleep_ms(500)

def apply_config():
    """Configure the module using AT commands."""
    ip_mode = "1" if USE_DHCP else "0"

    if MODE == "uart":
        print("[CFG] Entering AT mode (UART)...")
        _enter_at_mode_uart()

    # 1. Apply basic network and security settings
    cmds = [
        ("OP", "6"),            # MQTTS Mode (SSL/TLS)
        ("IM", ip_mode),        # IP Mode (0:Static, 1:DHCP)
        ("RH", BROKER_HOST),    # Remote Host (AWS IoT Endpoint)
        ("RP", BROKER_PORT),    # Remote Port
        ("PU", PUB_TOPIC),      # MQTT Publish Topic
        ("U0", SUB_TOPIC),      # MQTT Subscribe Topic
        ("QC", CLIENT_ID),      # MQTT Client ID
        ("KA", "1"),            # Keep-Alive Enable
        ("QK", str(KEEP_ALIVE)),# Keep-Alive Interval
        ("PT", "10"),           # Packet Transmission Time
        ("RC", "2"),            # Root CA Verify Required
        ("CE", "1"),            # Client Certificate Enable
        ("DG", "2"),            # Debug Message Enable
    ]

    # Add Static IP settings if not using DHCP
    if not USE_DHCP:
        cmds.extend([
            ("LI", LOCAL_IP),
            ("SM", SUBNET_MASK),
            ("GW", GATEWAY),
            ("DS", DNS_SERVER),
        ])

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

    # Save and reboot before cert upload (UART only)
    # Re-enter AT mode after reboot to upload certificates
    if MODE == "uart":
        print("[CFG] Saving (SV)...")
        s2e.send_cmd("SV", "")
        time.sleep_ms(500)

        print("[CFG] Rebooting (RT)...")
        s2e.send_cmd("RT", "")

        print(f"[CFG] Waiting {AFTER_RT_WAIT_MS/1000}s for boot...")
        time.sleep_ms(AFTER_RT_WAIT_MS)

        print("[CFG] Re-entering AT mode for certificate upload...")
        _enter_at_mode_uart()

    # 2. Upload certificates
    upload_certs()

    # Save and reboot to apply all settings including certificates
    print("[CFG] Saving (SV)...")
    s2e.send_cmd("SV", "")
    time.sleep_ms(500)

    print("[CFG] Rebooting (RT)...")
    s2e.send_cmd("RT", "")

    print(f"[CFG] Waiting {AFTER_RT_WAIT_MS/1000}s for boot & TLS handshake...")
    time.sleep_ms(AFTER_RT_WAIT_MS)

def mqtt_communication():
    """Main loop to handle MQTTS data stream."""
    time.sleep_ms(500)

    # Send initial publish message
    print("[MQTTS] Sending initial message...")
    s2e.send_data(PUB_MESSAGE)

    buf          = b""
    last_rx_time = None

    while True:
        try:
            res = s2e.recv_data() if MODE == "spi" else s2e.recv_data_mv()

            if isinstance(res, tuple):
                mv, n = res
                if n > 0:
                    buf         += bytes(mv[:n])
                    last_rx_time = time.ticks_ms()

            # Flush buffer once no new data received within PACKET_WAIT_MS
            if buf and last_rx_time is not None:
                if time.ticks_diff(time.ticks_ms(), last_rx_time) >= PACKET_WAIT_MS:
                    raw = buf.decode('utf-8', 'ignore').strip()
                    if " : " in raw:
                        print(f"[RX] {raw}")
                    else:
                        print(f"[RX] {SUB_TOPIC} : {raw}")
                    buf          = b""
                    last_rx_time = None

        except Exception as e:
            if "Timeout" not in str(e):
                print(f"[WARN] Comm Error: {e}. Retrying...")
            time.sleep_ms(10)

def main():
    s2e.print_info()
    # s2e.print_help()

    # 1. Setup
    apply_config()

    # 2. Start MQTTS communication
    mqtt_communication()

if __name__ == "__main__":
    main()

