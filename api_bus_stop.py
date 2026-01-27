import urequests
import time
import utime
import json
from my_secrets import API_KEY, STOP_ID  # STOP_ID here is the fallback
import gc

STOP_MONITORING_URL = "https://bustime.mta.info/api/siri/stop-monitoring.json"

def get_dynamic_local_offset():
    t = time.localtime()
    month, day, weekday = t[1], t[2], t[6]
    if month < 3 or month > 11: return -5 * 3600
    if month > 3 and month < 11: return -4 * 3600
    if month == 3:
        if day < 8: return -5 * 3600
        if day > 14: return -4 * 3600
        if day - weekday >= 8: return -4 * 3600
        return -5 * 3600
    if month == 11:
        if day > 7: return -5 * 3600
        if day - weekday >= 1: return -5 * 3600
        return -4 * 3600

def current_time_str():
    offset = get_dynamic_local_offset()
    t = time.localtime(time.time() + offset)
    hour, minute = t[3], t[4]
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12
    if display_hour == 0: display_hour = 12
    return "{}:{:02d} {}".format(display_hour, minute, suffix)

def parse_eta(eta_raw):
    try:
        t_part = eta_raw.split("T")[1]
        hms = t_part.split(":")
        hour, minute = int(hms[0]), int(hms[1])
        suffix = "AM" if hour < 12 else "PM"
        display_hour = hour % 12
        if display_hour == 0: display_hour = 12
        return "{}:{:02d} {}".format(display_hour, minute, suffix)
    except: return None

def compute_minutes_away(eta_raw):
    try:
        t_str = eta_raw[:19]
        year, month, day = int(t_str[0:4]), int(t_str[5:7]), int(t_str[8:10])
        hour, minute, second = int(t_str[11:13]), int(t_str[14:16]), int(t_str[17:19])
        eta_secs = utime.mktime((year, month, day, hour, minute, second, 0, 0, -1))
        offset = get_dynamic_local_offset()
        now_secs = utime.time() + offset
        delta_seconds = eta_secs - now_secs
        return max(int((delta_seconds / 60) + 0.5), 0)
    except: return 0

def extract_time_from_text(text):
    try:
        if "scheduled to depart" not in text: return None
        after = text.split("scheduled to depart")[1].strip()
        tokens = after.split()
        for i in range(len(tokens)):
            if ':' in tokens[i]:
                return tokens[i] + " " + tokens[i+1].replace(")", "")
        return None
    except: return None

def compute_minutes_from_ampm(time_str):
    try:
        hour_min, suffix = time_str.split()
        hour, minute = [int(x) for x in hour_min.split(":")]
        if suffix == "PM" and hour != 12: hour += 12
        if suffix == "AM" and hour == 12: hour = 0
        now = time.localtime(time.time() + get_dynamic_local_offset())
        target_total = hour * 60 + minute
        now_total = now[3] * 60 + now[4]
        delta = target_total - now_total
        if delta < -600: delta += 1440 
        return delta
    except: return -1

class BusData:
    def __init__(self, line, destination, eta_raw, distance_away, stops_away, bus_id, stop_name):
        self.line = line
        self.destination = destination
        self.bus_id = bus_id
        self.stop_name = stop_name
        self.distance_away = distance_away
        self.stops_away = stops_away
        self.eta = parse_eta(eta_raw) if eta_raw else None
        self.minutes_away = compute_minutes_away(eta_raw) if eta_raw else 0 # Fallback to 0

        sched_time = extract_time_from_text(distance_away)
        if sched_time:
            sched_min = compute_minutes_from_ampm(sched_time)
            if self.minutes_away == 0 and sched_min > 0:
                self.eta = sched_time
                self.minutes_away = sched_min

    def short_string(self):
        return "{}: {} min".format(self.line, self.minutes_away)

def get_realtime_bus_updates(target_stop=None):
    # FALLBACK LOGIC: 
    # Use the target_stop (from config), or fall back to STOP_ID (from secrets)
    final_stop_id = target_stop if target_stop else STOP_ID
    
    url = "{}?key={}&MonitoringRef={}".format(STOP_MONITORING_URL, API_KEY, final_stop_id)
    
    #clear memory
    gc.collect()
    try:
        response = urequests.get(url)
        data = response.json()
        
        # keep memory tidy. deltete the raw json response.
        response.close()
        del response
        
        busses = []
        delivery = data["Siri"]["ServiceDelivery"]["StopMonitoringDelivery"][0]
        visits = delivery.get("MonitoredStopVisit", [])
        
        for visit in visits:
            journey = visit["MonitoredVehicleJourney"]
            call = journey["MonitoredCall"]
            dist = call["Extensions"]["Distances"]
            
            bus = BusData(
                line=journey["PublishedLineName"],
                destination=journey["DestinationName"],
                eta_raw=call.get("ExpectedArrivalTime"),
                distance_away=dist["PresentableDistance"],
                stops_away=dist.get("StopsFromCall", 0),
                bus_id=journey.get("VehicleRef", "N/A"),
                stop_name=call["StopPointName"]
            )
            busses.append(bus)
        
        # Now that we have the busses list of objects, delete the data
        del data
        gc.collect()
        
        return busses
    except Exception as e:
        print("❌ API Error:", e)
        return []
