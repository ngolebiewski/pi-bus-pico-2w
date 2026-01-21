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
REFRESH_INTERVAL = 30  # seconds between API fetches
PAGE_TIME = 3           # seconds per bus display

# --- Global State ---
stop_index = 0
display_mode = 0  # 0..len(stop_ids)-1 = single stops, last = all stops
last_api_request_time = 0
busses = []
skip_next_animation = False
config = {}

# --------------------------
# --- Helper Functions ---
# --------------------------

def sync_time():
    """Sync time via NTP with retries"""
    for i in range(4):
        try:
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
    """Handle short/long presses and setup mode"""
    global stop_index, display_mode, last_api_request_time, skip_next_animation, config

    if button.value() == 0:
        led.on()
        press_start = time.time()
        is_long_press = False

        while button.value() == 0:
            if time.time() - press_start >= 2:
                is_long_press = True
                print("🚀 Entering Setup Mode")
                setup_result = run_setup()
                if setup_result is False:
                    lcd.clear()
                    lcd.message("Setup Cancelled\nResuming...")
                    time.sleep(2)
                print("⬅️ Returned from Setup")
                last_api_request_time = 0
                led.off()
                return True
            time.sleep(0.05)

        led.off()

        # SHORT PRESS: cycle stops -> all stops
        if not is_long_press:
            stop_ids = config.get("stop_ids", [])
            num_stops = len(stop_ids)
            if num_stops == 0:
                return False

            display_mode = (display_mode + 1) % (num_stops + 1)
            if display_mode < num_stops:
                stop_index = display_mode
                lcd.clear()
                lcd.message(f"Switching to\nStop {stop_index + 1}")
                print(f"🔄 Single stop: {stop_index}")
            else:
                stop_index = -1  # all stops
                lcd.clear()
                lcd.message("Switching to\nALL stops")
                print("🔄 Display all stops")

            last_api_request_time = 0
            skip_next_animation = True
            time.sleep(0.5)
            return True
    return False

def block_animation_lcd(duration=2):
    """Bus animation; can be skipped on manual stop switch"""
    global skip_next_animation
    if skip_next_animation:
        skip_next_animation = False
        return

    block_char = chr(219)
    wheel_char = "0"
    delay = duration / 19

    for pos in range(-3, 17):
        if check_button():
            break
        top = "".join([block_char if pos <= i < pos + 3 else " " for i in range(16)])
        bot = "".join([wheel_char if i == pos or i == pos + 2 else " " for i in range(16)])
        lcd.clear()
        lcd.message(top + "\n" + bot)
        time.sleep(delay)

def display_busses(bus_list):
    """Show buses on LCD, interruptible by button"""
    if not bus_list:
        lcd.clear()
        lcd.message("No upcoming\nbuses")
        time.sleep(PAGE_TIME)
        return

    # Cap display to avoid memory spikes
    valid_busses = [b for b in bus_list if b.minutes_away > 0][:30]

    for bus in valid_busses:
        stop_name = bus.stop_name[:16]
        line = f"{bus.line} {bus.minutes_away} min"
        lcd.clear()
        lcd.message(stop_name + "\n" + line)
        print(f"📺 {stop_name} | {line}")
        for _ in range(int(PAGE_TIME * 10)):
            if check_button():
                return
            time.sleep(0.1)

# --------------------------
# --- Startup ---
# --------------------------
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
lcd.clear()

# --------------------------
# --- Main Loop ---
# --------------------------
while True:
    stop_ids = config.get("stop_ids", [])
    if not stop_ids:
        run_setup()
        continue

    # 1. NEW LOGIC: Check if it's time to refresh, regardless of mode
    if time.time() - last_api_request_time > REFRESH_INTERVAL:
        
        if stop_index == -1:
            # ALL stops mode: fetch each stop individually and merge safely
            merged_busses = []
            print("🌐 Refreshing ALL stops...")
            for stop in stop_ids:
                try:
                    stop_busses = get_realtime_bus_updates(stop)
                    valid_busses = [b for b in stop_busses if b.minutes_away > 0][:6]
                    merged_busses.extend(valid_busses)
                except Exception as e:
                    print(f"❌ API Error fetching {stop}: {e}")
            
            merged_busses.sort(key=lambda b: b.minutes_away)
            busses = merged_busses # Update the global list

        else:      
            # Single stop mode
            current_stop = stop_ids[stop_index]
            try:
                print(f"🌐 Refreshing Single Stop: {current_stop}")
                busses = get_realtime_bus_updates(current_stop)
            except Exception as e:
                print(f"❌ API Error: {e}")
                busses = []

        # Update the timestamp after the refresh is done
        last_api_request_time = time.time()
        block_animation_lcd()

    # 2. Always display whatever is in the current 'busses' list
    display_busses(busses)

