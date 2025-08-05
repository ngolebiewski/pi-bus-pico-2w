from LCD1602 import LCD
import time
from api_bus_stop import get_realtime_bus_updates, current_time_str
from wifi_util import wifi_connect
from my_secrets import *
import ntptime # Micro Python library
import time

def local_time():
    return time.localtime(time.time() + LOCAL_OFFSET)

def sync_time():
    try:
        ntptime.settime()
        print("✅ Time synced")
    except:
        print("❌ Failed to sync time")


lcd = LCD()
lcd.clear()
lcd.message("Connecting WiFi\nPlease wait...")

ssid = wifi_connect()
time.sleep(2)
sync_time()

lcd.clear()

REFRESH_INTERVAL = 30  # seconds

def block_animation_lcd(line_length=16, duration=1):
    block_char = chr(219)  # Full block character
    frames = line_length
    delay = duration / frames

    for pos in range(frames):
        # Build the line with spaces except the block at pos
        line = " " * pos + block_char + " " * (line_length - pos - 1)

        lcd.clear()
        lcd.message(line + "\n")  # Clear and write block line on first LCD line
        time.sleep(delay)

    # Optionally clear after animation
    lcd.clear()

def display_stop_name(stop_name):
    # Show stop name on both lines, split if needed
    line1 = stop_name[:16]
    line2 = stop_name[16:32] if len(stop_name) > 16 else stop_name[:16]
    lcd.clear()
    lcd.message(line1 + "\n" + line2)
    print("Stop name:\n" + line1 + "\n" + line2)

def display_bus_times(busses):
    # Show up to 2 buses line + time on separate lines
    lcd.clear()
    for i in range(len(busses)):
        if i < len(busses):
            bus = busses[i]
            line = "{} {}".format(bus.line, str(bus.minutes_away) + " min")
        else:
            line = ""
        if i == 0:
            lcd.message(line + "\n")
        else:
            lcd.message(line)
        print(line)

def update_lcd_stop_then_bus():
    try:
        busses = get_realtime_bus_updates()
        if not busses:
            lcd.clear()
            lcd.message("No bus data\nTry again soon")
            print("No bus data, try again soon")
            return

        stop_name = busses[0].stop_name


        for _ in range((REFRESH_INTERVAL + 8 - 1) // 8):
            # Step 1: Show stop name for 2 seconds
            display_stop_name(stop_name)
            time.sleep(2)

            # Step 2: Show bus times for 6 seconds (you can adjust timing)
            display_bus_times(busses)
            time.sleep(6)

    except Exception as e:
        lcd.clear()
        lcd.message("Error occurred\nCheck WiFi/API")
        print("❌ Error:", e)
        
def update_lcd():
    BUS_ETA_DISPLAY_TIME = 2
    try:
        busses = get_realtime_bus_updates()
        if not busses:
            lcd.clear()
            lcd.message("No bus data\nTry again soon")
            print("No bus data, try again soon")
            return

        stop_name = busses[0].stop_name[:16]  # Trim to 16 chars to fit LCD line
        
        num_busses_timing = len(busses)*BUS_ETA_DISPLAY_TIME
        
        for _ in range((REFRESH_INTERVAL + num_busses_timing - 1) // num_busses_timing):
            # Cycle through each bus, show stop name on line 1, bus line + time on line 2
            for bus in busses:
                lcd.clear()
                line2 = "{} {} min".format(bus.line, bus.minutes_away)
                lcd.message(stop_name + "\n" + line2)
                print(stop_name)
                print(line2)
                time.sleep(2)

    except Exception as e:
        lcd.clear()
        lcd.message("Error occurred\nCheck WiFi/API")
        print("❌ Error:", e)

# Initial display
lcd.message(f"Connected to\n{ssid}")
time.sleep(2)
lcd.clear()
lcd.message(f"Starting up\n:)")
time.sleep(2)
lcd.clear()

# Main loop
while True:
    update_lcd()
    block_animation_lcd()
    
    # time.sleep(REFRESH_INTERVAL - 8)  # subtract time spent displaying so approx 45s total




# from LCD1602 import LCD
# import time
# from api_bus_stop import get_realtime_bus_updates, current_time_str
# from wifi_util import wifi_connect
# from my_secrets import *
# 
# lcd = LCD()
# lcd.clear()
# lcd.message("Connecting WiFi\nPlease wait...")
# 
# wifi_connect()
# time.sleep(2)
# 
# lcd = LCD()
# lcd.clear()
# 
# last_bus_ids = set()
# 
# REFRESH_INTERVAL = 45  # seconds
# 
# def format_lcd_display(busses):
#     if not busses:
#         return ("No bus data", "Try again soon")
# 
#     line = busses[0].line
#     stop = busses[0].stop_name
# 
#     # First line: Bus | Stop
#     line1 = "{} | {}".format(line, stop[:12])  # Trim stop name to fit
# 
#     # Second line: Arrival times (up to 2 buses)
#     times = [str(bus.minutes_away) + " min" for bus in busses[:2]]
#     line2 = " & ".join(times)
#     
#     return (line1, line2)
# 
# def update_lcd_basic():
#     try:
#         busses = get_realtime_bus_updates()
# 
#         # If no data
#         if not busses:
#             lcd.clear()
#             lcd.message("No bus data\nTry again soon")
#             return
# 
#         line1, line2 = format_lcd_display(busses)
# 
#         lcd.clear()
#         lcd.message(line1 + "\n" + line2)
#         print("🚌", line1 + " — " + line2)
# 
#     except Exception as e:
#         lcd.clear()
#         lcd.message("Error occurred\nCheck WiFi/API")
#         print("❌ Error:", e)
# 
# 
# def update_lcd():
#     try:
#         busses = get_realtime_bus_updates()
# 
#         if not busses:
#             lcd.clear()
#             lcd.message("No bus data\nTry again soon")
#             return
# 
#         line = busses[0].line
#         stop = busses[0].stop_name
#         times = [str(bus.minutes_away) + " min" for bus in busses[:2]]
#         line2 = " & ".join(times)
# 
#         base = "{} ".format(line)
#         scroll_text = base + stop
#         full_length = len(scroll_text)
# 
#         if full_length <= 16:
#             # No scrolling needed
#             lcd.clear()
#             lcd.message(scroll_text + "\n" + line2)
#             print("🚌", scroll_text + " — " + line2)
#             return
# 
#         # Marquee scroll
#         for i in range(full_length - 15):
#             lcd.clear()
#             top_line = scroll_text[i:i+16]
#             lcd.message(top_line + "\n" + line2)
#             time.sleep(0.2)
# 
#         # After scrolling, pause on first frame
#         lcd.clear()
#         lcd.message(scroll_text[:16] + "\n" + line2)
#         print("🚌", scroll_text[:16] + " — " + line2)
# 
#     except Exception as e:
#         lcd.clear()
#         lcd.message("Error occurred\nCheck WiFi/API")
#         print("❌ Error:", e)
# 
#     except Exception as e:
#         lcd.clear()
#         lcd.message("Error occurred\nCheck WiFi/API")
#         print("❌ Error:", e)
# 
# # Initial display
# lcd.message("Starting up...\nConnecting WiFi")
# time.sleep(2)
# 
# # Main loop
# while True:
#     update_lcd()
#     time.sleep(REFRESH_INTERVAL)
# 
