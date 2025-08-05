import urequests
import time
from my_secrets import API_KEY, STOP_ID, LOCAL_OFFSET


STOP_MONITORING_URL = "https://bustime.mta.info/api/siri/stop-monitoring.json"

def current_time_str():
    t = time.localtime()
    hour = t[3]
    minute = t[4]
    suffix = "AM" if hour < 12 else "PM"
    hour = hour if 1 <= hour <= 12 else abs(hour - 12)
    return "{}:{:02d} {}".format(hour, minute, suffix)

def parse_eta(eta_raw):
    try:
        date_part, time_part = eta_raw.split("T")
        hms = time_part.split(":")
        hour = int(hms[0])
        minute = int(hms[1])
        suffix = "AM" if hour < 12 else "PM"
        hour = hour if 1 <= hour <= 12 else abs(hour - 12)
        return "{}:{:02d} {}".format(hour, minute, suffix)
    except:
        return None

LOCAL_OFFSET = -4 * 60 * 60  # UTC-4 in seconds

def compute_minutes_away(eta_raw):
    try:
        date_part, time_part = eta_raw.split("T")
        hms = time_part.split(":")
        eta_hour = int(hms[0])
        eta_min = int(hms[1])
        eta_total = eta_hour * 60 + eta_min

        # Adjust local time properly
        now = time.localtime(time.time() + LOCAL_OFFSET)
        now_total = now[3] * 60 + now[4]

        delta = eta_total - now_total
        return max(int(delta), 0)
    except:
        return -1


def extract_time_from_text(text):
    # Extracts time like "12:25 PM" from text containing 'scheduled to depart'
    try:
        parts = text.split("scheduled to depart")
        if len(parts) < 2:
            return None
        # Take the substring after 'scheduled to depart'
        after = parts[1].strip()
        # Expected format: "... at 12:25 PM)"
        # We'll find the first occurrence of HH:MM AM/PM using simple parsing
        tokens = after.split()
        for i in range(len(tokens)):
            # Look for token with ':' indicating time
            if ':' in tokens[i]:
                # Next token should be AM or PM
                if i+1 < len(tokens) and tokens[i+1] in ("AM", "PM"):
                    return tokens[i] + " " + tokens[i+1]
        return None
    except:
        return None

def compute_minutes_from_ampm(time_str):
    try:
        hour_min, suffix = time_str.split()
        hour, minute = [int(x) for x in hour_min.split(":")]

        if suffix == "PM" and hour != 12:
            hour += 12
        if suffix == "AM" and hour == 12:
            hour = 0

        target_total = hour * 60 + minute

        now = time.localtime(time.time() + LOCAL_OFFSET)
        now_total = now[3] * 60 + now[4]

        delta = target_total - now_total
        if delta < 0:
            delta += 24 * 60  # wrap around to next day

        return delta
    except:
        return -1

class BusData:
    def __init__(self, line, destination, eta_raw, distance_away, stops_away, bus_id, stop_name):
        self.line = line
        self.destination = destination
        self.bus_id = bus_id
        self.stop_name = stop_name
        self.distance_away = distance_away
        self.stops_away = stops_away

        # Default ETA and minutes away from ExpectedArrivalTime
        self.eta = parse_eta(eta_raw) if eta_raw else None
        self.minutes_away = compute_minutes_away(eta_raw) if eta_raw else None

        # Try to extract scheduled departure time from distance_away text
        if distance_away and "scheduled to depart" in distance_away:
            sched_time = extract_time_from_text(distance_away)
            if sched_time:
                sched_minutes_away = compute_minutes_from_ampm(sched_time)
                # If ETA is wrong (like 2 min but scheduled is 10 min), use scheduled instead
                if self.minutes_away is None or sched_minutes_away > self.minutes_away:
                    self.eta = sched_time
                    self.minutes_away = sched_minutes_away



    def short_string(self):
        if self.eta is None:
            return "{}: {}".format(self.line, self.distance_away)
        else:
            return "{}: {} min (ETA {})".format(self.line, self.minutes_away, self.eta)

def get_realtime_bus_updates():
    url = "{}?key={}&MonitoringRef={}".format(STOP_MONITORING_URL, API_KEY, STOP_ID)
    try:
        response = urequests.get(url)
        data = response.json()
        response.close()
    except Exception as e:
        print("❌ Network or parsing error:", e)
        return []

    busses = []
    try:
        visits = data["Siri"]["ServiceDelivery"]["StopMonitoringDelivery"][0].get("MonitoredStopVisit", [])
        for visit in visits[:3]:
            journey = visit["MonitoredVehicleJourney"]
            call = journey["MonitoredCall"]
            dist = call["Extensions"]["Distances"]
            bus = BusData(
                line=journey["PublishedLineName"],
                destination=journey["DestinationName"],
                eta_raw=call.get("ExpectedArrivalTime", ""),
                distance_away=dist["PresentableDistance"],
                stops_away=dist["StopsFromCall"],
                bus_id=journey["VehicleRef"],
                stop_name=call["StopPointName"]
            )
            busses.append(bus)
    except KeyError as e:
        print("❌ Could not process real-time data. Missing key:", e)

    return busses

# Debug / Entry Point
if __name__ == "__main__":
    print("Fetching real-time MTA data at", current_time_str())
    buses = get_realtime_bus_updates()
    for bus in buses:
        print(bus.short_string())
