# 01_at_cmd_tester.py
import time

# -------------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------------
MODE = "uart"   # Set to "spi" or "uart"

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
# Helper: Enter AT Mode (UART Only)
# -------------------------------------------------------------------------
def enter_at_mode_uart():
    """
    Enter AT command mode for UART.
    Sequence: Guard Time (1s) -> Send '+++' -> Guard Time (1s)
    """
    print("[UART] Attempting to enter AT mode (Wait 1s -> +++ -> Wait 1s)...")
    time.sleep_ms(1000)  # Guard Time (Pre)
    s2e.send_data("+++") # Entry Command
    time.sleep_ms(1000)  # Guard Time (Post)
    print("[UART] Entry signal sent. Ready for commands.")

# -------------------------------------------------------------------------
# Main Logic
# -------------------------------------------------------------------------
def main():
    print(f"\n=== W55RP20 AT Command Tester ({MODE.upper()}) ===")
    
    # Print driver info
    try:
        s2e.print_info()
    except:
        pass

    # [Initialization Step]
    if MODE == "uart":
        enter_at_mode_uart()
    elif MODE == "spi":
        print("[SPI] Mode detected. Checking SPI connection...")
        try:
            ver = s2e.send_cmd("VR", "") 
            print(f"[SPI] Connection OK! Module response: {ver}")
        except Exception as e:
            print(f"[SPI] Connection Failed: {e}")
            return

    print("\n[Usage]")
    print(" - Input: MC -> [GET]")
    print(" - Input: LI192.168.11.37 -> [SET]")
    print(" - Help: ? or help")
    print(" - Exit: exit or quit")
    print("-" * 40)

    while True:
        try:
            # 1. Get user input
            user_input = input("AT> ").strip()

            if not user_input:
                continue

            # 2. Check for Help commands
            if user_input == "?" or user_input.lower() == "help":
                try: s2e.print_help()
                except: print("[INFO] print_help() is not available.")
                continue

            # 3. Check for Exit
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting program.")
                break
            
            # 4. Check for '+++' (UART Re-entry)
            if user_input == "+++":
                if MODE == "uart":
                    enter_at_mode_uart()
                else:
                    print("[INFO] SPI mode does not require '+++'.")
                continue

            # 5. Parsing Logic
            # Rule 1: First 2 characters are the Command.
            # Rule 2: Everything after is the Parameter.
            if len(user_input) < 2:
                print("[ERR] Command must be at least 2 characters.")
                continue

            cmd = user_input[:2].upper()      # First 2 chars
            param = user_input[2:].strip()    # Rest (stripped of whitespace)

            # 6. Send to Module
            result = s2e.send_cmd(cmd, param)
            
            # 7. Print Result with Labels
            # Determine label based on parameter existence
            if not param:
                # [GET] Case (No parameter)
                print(f"   [GET] {result}")
                
                # Add Explanations for specific action commands
                if cmd == "SV":
                    print("   (Settings Saved to Flash Memory)")
                elif cmd == "RT":
                    print("   (Module Rebooting... Please wait)")
            else:
                # [SET] Case (With parameter)
                print(f"   [SET] {result}")
                # Print reminder for SET operations
                print("   [NOTE] Use 'SV' to save settings.")
                print("   [NOTE] Use 'RT' to apply changes such as:")
                print("          1. IP Allocation methods (Static <-> DHCP)")
                print("          2. Operation Mode changes")
                print("          3. Other startup configurations")
            
            # Warning if user exited AT mode (UART only)
            if MODE == "uart" and cmd == "EX":
                print("[WARN] Exited AT mode (Switched to Data Mode).")
                print("       Type '+++' to re-enter AT mode.")

        except KeyboardInterrupt:
            print("\nInterrupted.")
            break
        except Exception as e:
            print(f"[ERROR]: {e}")

if __name__ == "__main__":
    main()
