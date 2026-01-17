import network
import socket
import json
import machine
import time
from machine import Pin

# Setup LED
led = Pin("LED", Pin.OUT)

def url_unquote(text):
    if not text: return ""
    res = text.replace('+', ' ')
    parts = res.split('%')
    if len(parts) == 1: return res
    result = parts[0]
    for part in parts[1:]:
        if len(part) >= 2:
            try:
                char = chr(int(part[:2], 16))
                result += char + part[2:]
            except:
                result += '%' + part
        else:
            result += '%' + part
    return result

def rssi_to_bars(rssi):
    if rssi >= -50: return "📶📶📶📶"
    if rssi >= -65: return "📶📶📶"
    if rssi >= -80: return "📶📶"
    return "📶"

def scan_wifi():
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        results = sta.scan()
        results.sort(key=lambda x: x[3], reverse=True)
        unique_nets = []
        seen_ssids = set()
        for res in results:
            ssid = res[0].decode('utf-8')
            if ssid and ssid not in seen_ssids:
                unique_nets.append((ssid, rssi_to_bars(res[3])))
                seen_ssids.add(ssid)
        return unique_nets
    except:
        return [("Scan Failed", "❌")]

def serve():
    button = Pin(22, Pin.IN, Pin.PULL_UP)
    try:
        from LCD1602 import LCD
        lcd = LCD()
    except:
        lcd = None

    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except:
        config = {"networks": {}, "stop_ids": []}
        
    existing_stops = ",".join(config.get("stop_ids", []))
    
    ap = network.WLAN(network.AP_IF)
    ap.config(essid="Pi-Bus-Setup", password="pibusbox")
    ap.active(True)

    found_nets = scan_wifi()
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    s.settimeout(0.2) 

    instructions = [
        "Join:Pi-Bus-Set ", 
        "Pass:pibusbox   ",
        "Try AirplaneMode",
        "Go: 192.168.4.1 "
    ]
    instr_idx = 0
    last_instr_change = time.ticks_ms()

    while True:
        led.toggle()
        
        if lcd and time.ticks_diff(time.ticks_ms(), last_instr_change) > 2500:
            lcd.clear()
            lcd.message("SETUP: ACTIVE\n" + instructions[instr_idx])
            instr_idx = (instr_idx + 1) % len(instructions)
            last_instr_change = time.ticks_ms()

        if button.value() == 0:
            press_start = time.time()
            while button.value() == 0:
                if time.time() - press_start >= 2:
                    led.off()
                    network.WLAN(network.AP_IF).active(False)
                    return False 
                time.sleep(0.05)

        try:
            cl, addr = s.accept()
            led.on()
            request = cl.recv(1024).decode('utf-8')
            
            if 'GET /?' in request:
                query = request.split('GET /?')[1].split(' ')[0]
                params = {pk.split('=')[0]: url_unquote(pk.split('=')[1]) for pk in query.split('&') if '=' in pk}
                
                # 1. Update Stop IDs (Always happens)
                config["stop_ids"] = [s.strip() for s in params['bus_stop'].split(',')]
                
                # 2. Update WiFi (Only if a specific network was chosen)
                selected_ssid = params.get('ssid', 'SKIP')
                wifi_pass = params.get('wifi_pass', '')

                if selected_ssid != "SKIP":
                    # Add new network to the dictionary (keeps existing ones!)
                    config["networks"][selected_ssid] = wifi_pass
                
                with open("config.json", "w") as f:
                    json.dump(config, f)
                
                cl.send('HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n')
                cl.send('<html><body><h1>Saved!</h1><p>Rebooting...</p></body></html>')
                cl.close()
                machine.reset()
            
            else:
                # Add a "SKIP" option as the first item in the dropdown
                wifi_options = '<option value="SKIP">--- No Change / Skip ---</option>'
                wifi_options += "".join([f'<option value="{n[0]}">{n[1]} {n[0]}</option>' for n in found_nets])
                
                html = f"""<!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body {{ background: #0f172a; color: #f8fafc; font-family: sans-serif; padding: 15px; }}
                        .card {{ background: #1e293b; padding: 20px; border-radius: 16px; max-width: 400px; margin: auto; }}
                        h1 {{ color: #38bdf8; font-size: 22px; text-align: center; }}
                        label {{ display: block; margin: 15px 0 5px; color: #94a3b8; font-size: 14px; }}
                        select, input {{ width: 100%; padding: 12px; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 8px; box-sizing: border-box; font-size: 16px; margin-bottom: 10px; }}
                        .btn {{ background: #38bdf8; color: #0f172a; border: none; padding: 16px; width: 100%; border-radius: 8px; font-weight: bold; margin-top: 15px; cursor: pointer; }}
                        .note {{ font-size: 12px; color: #94a3b8; margin-top: 5px; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h1>🚌 Pi Bus Setup</h1>
                        <form action="/" accept-charset="utf-8">
                            <label>Add New WiFi (Optional)</label>
                            <select name="ssid">{wifi_options}</select>
                            <input name="wifi_pass" type="password" placeholder="WiFi Password">
                            
                            <label>Bus Stop IDs (comma sep)</label>
                            <input name="bus_stop" value="{existing_stops}">
                            <div class="note">Currently saved stops: {len(config.get('stop_ids',[]))}</div>
                            
                            <button class="btn" type="submit">SAVE & REBOOT</button>
                        </form>
                    </div>
                </body>
                </html>"""
                
                cl.send('HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=UTF-8\r\n\r\n' + html)
                cl.close()
        except (OSError, IndexError):
            pass
