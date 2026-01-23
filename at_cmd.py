# main.py
import time

MODE = "spi"        # "spi" or "uart"
AT_CMD = "LI" 
AT_PARAM = ""

if MODE == "spi":
    import w55rp20_s2e_spi as s2e
elif MODE == "uart":
    import w55rp20_s2e_uart as s2e
else:
    raise ValueError("MODE must be 'spi' or 'uart'")

# Common logic
s2e.print_info()
s2e.print_help()

while True:
    try:
        result = s2e.send_cmd(AT_CMD, AT_PARAM)
        print(result)
        time.sleep_ms(1000)
    except Exception as e:
        print(f"[ERROR]: {e}")
