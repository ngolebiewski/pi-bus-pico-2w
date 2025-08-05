import network # Micro Python Library
import time
import urequests
from my_secrets import KNOWN_NETWORKS

def check_networks():
    # Create a station interface
    wlan = network.WLAN(network.STA_IF)

    # Activate the interface
    wlan.active(True)

    # Scan for networks
    networks = wlan.scan()

    # Wait a moment for the scan to complete
    time.sleep(1)

    # Check if any networks were found
    if networks:
        print("Found {} network(s):".format(len(networks)))
        print("-" * 40)
        print("{:<25} {:<5} {:<10}".format("SSID", "Channel", "RSSI"))
        print("-" * 40)
        
        # Iterate through the list of networks and print the information
        for net in networks:
            ssid = net[0].decode('utf-8')  # Decode the SSID from bytes to a string
            channel = net[2]
            rssi = net[3]
            print("{:<25} {:<5} {:<10}".format(ssid, channel, rssi))
    else:
        print("No networks found.")


def wifi_connect():
    # Store your network credentials in a dictionary
    # The format is { "SSID": "password" }
    known_networks = KNOWN_NETWORKS

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Loop through the known networks and try to connect
    for ssid, password in known_networks.items():
        print(f"Trying to connect to {ssid}...")
        wlan.connect(ssid, password)
        
        # Wait for the connection
        wait_time = 10
        while wait_time > 0:
            if wlan.isconnected():
                break
            wait_time -= 1
            time.sleep(1)
            
        if wlan.isconnected():
            print(f"Successfully connected to {ssid}!")
            print('IP address:', wlan.ifconfig()[0])
            return ssid
            break # Exit the loop once a connection is made
        else:
            print(f"Failed to connect to {ssid}.")
        
        

    # Final check
    if not wlan.isconnected():
        print("Could not connect to any known network.")
        
    return None

def test_call():
    try:
        # This URL returns simple JSON — great for basic testing
        response = urequests.get("https://jsonplaceholder.typicode.com/posts/1")
        data = response.json()
        response.close()
        
        print("Test successful! Title of post 1:")
        print(data["title"])
        return data["title"]

    except Exception as e:
        print("Failed to fetch data:", e)
        return None

    
if __name__ == "__main__":
    check_networks()
    wifi_connect()
    test_call()
    
    
