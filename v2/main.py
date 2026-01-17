from machine import Pin
import time
import json
import ntptime
from LCD1602 import LCD
from api_bus_stop import get_realtime_bus_updates, current_time_str
from wifi_util import wifi_connect
from serve import serve as run_setup

# --- Hardware Setup ---
button = Pin(22, Pin.IN, Pin.PULL_UP)
led = Pin("LED", Pin.OUT)
lcd = LCD()

# --- Global Settings ---
REFRESH_INTERVAL = 30  
PAGE_TIME = 3          

# --- Global State ---
stop_index = 0
last_api_request_time = 0
busses = []
skip_next_animation = False # New flag to bypass the bus drive-by

def sync_time():
    """Retries NTP sync up to 4 times."""
    for i in range(4):
        try:
            print(f"Syncing time (Attempt {i+1}/3)...")
            ntptime.settime()
            print("✅ Time synced successfully")
            return True
        except Exception as e:
            print(f"❌ Sync failed: {e}")
            time.sleep(2)
    return False

def load_config():
    try:
        with open("config.json", "r") as f:
            data = json.load(f)
            print("📂 Config loaded:", data)
            return data
    except Exception as e:
        print("⚠️ No config.json found.")
        return {"networks": {}, "stop_ids": []}

def check_button():
    global stop_index, last_api_request_time, config, skip_next_animation
    
    if button.value() == 0: 
        led.on()
        print("🔘 Button Pressed")
        press_start = time.time()
        is_long_press = False
        
        # Monitor how long the button is held
        while button.value() == 0:
            if time.time() - press_start >= 2:
                is_long_press = True
                print("🚀 Entering Setup Mode")
                
                # Code blocks here until user saves or holds button again
                setup_result = run_setup() 
                
                # Handle the return from setup mode
                if setup_result is False:
                    lcd.clear()
                    lcd.message("Setup Cancelled\nResuming...")
                    time.sleep(2)
                
                print("⬅️ Returned from Setup")
                last_api_request_time = 0 # Force a fresh data fetch
                return True # Exit check so we don't trigger a stop-switch too
            time.sleep(0.05)
        
        led.off()
        
        # --- SHORT PRESS LOGIC (Restore this part) ---
        if not is_long_press:
            stop_ids = config.get("stop_ids", [])
            if len(stop_ids) > 1:
                stop_index = (stop_index + 1) % len(stop_ids)
                last_api_request_time = 0 
                skip_next_animation = True # Don't show bus, show data instantly
                
                print(f"🔄 Switched to stop index: {stop_index}")
                lcd.clear()
                lcd.message(f"Switching to\nStop {stop_index + 1}")
                time.sleep(0.5)
                return True
    return False

def block_animation_lcd(duration=2):
    # Check the flag: if we just switched stops, don't play animation
    global skip_next_animation
    if skip_next_animation:
        print("⏩ Skipping animation (Manual Switch)")
        skip_next_animation = False # Reset for next time
        return

    print("🚌 Playing bus animation...")
    block_char = chr(219)
    wheel_char = "0"
    delay = duration / 19 # 16 chars + 3 bus width

    for pos in range(-3, 17):
        if check_button(): break 
        top = "".join([block_char if pos <= i < pos + 3 else " " for i in range(16)])
        bot = "".join([wheel_char if i == pos or i == pos + 2 else " " for i in range(16)])
        lcd.clear()
        lcd.message(top + "\n" + bot)
        time.sleep(delay)

# --- Startup ---
print("--- PiBus Starting Up ---")
lcd.clear()
lcd.message("Connecting WiFi\nPlease wait...")

ssid = wifi_connect()
if not ssid:
    run_setup()

sync_time()
config = load_config()

lcd.clear()
lcd.message(f"Connected to\n{ssid}")
time.sleep(1.5)

# --- Main Loop ---
while True:
    stop_ids = config.get("stop_ids", [])
    if not stop_ids:
        run_setup()

    current_stop = stop_ids[stop_index]

    if time.time() - last_api_request_time > REFRESH_INTERVAL:
        print(f"🌐 Fetching: {current_stop}")
        busses = get_realtime_bus_updates(current_stop)
        last_api_request_time = time.time()
        
        # This will only play if it was a timed refresh, not a button press
        block_animation_lcd()

    if busses:
        # 1. Filter out 0/negative (ghosts) and cap at 3
        # This prevents the list from flooding your screen
        valid_busses = [b for b in busses if b.minutes_away > 0][:6]
        
    if not valid_busses:
        lcd.clear()
        lcd.message("No upcoming\nbuses")
        time.sleep(3)
        continue

    stop_name = valid_busses[0].stop_name[:16]
    
    for bus in valid_busses:
        display_line = f"{bus.line} {bus.minutes_away} min"
        print(f"📺 {stop_name} | {display_line}")
        
        lcd.clear()
        lcd.message(stop_name + "\n" + display_line)
        
        # Wait 3 seconds per bus, but allow button to interrupt
        for _ in range(30): 
            if check_button(): break 
            time.sleep(0.1)
            
        # If button forced a refresh (last_api_request_time reset to 0)
        if last_api_request_time == 0: break    
    else:
        print("💤 No bus data.")
        lcd.clear()
        lcd.message("No bus data")
        for _ in range(30):
            if check_button(): break
            time.sleep(0.1)
