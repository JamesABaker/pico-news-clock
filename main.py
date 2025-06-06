from picographics import PicoGraphics, DISPLAY_INKY_PACK
import utime

# Lets connect to the internert and g
import ujson
import network
import urequests
from machine import RTC
import utime

# Global variables
# Initialize the display - specify a compatible pen type
display = PicoGraphics(display=DISPLAY_INKY_PACK)

# Draw some basic text with proper parameters
display.set_pen(0)  # Set pen to black
# Pause for a second

last_collected_time = None  # Variable to store the last collected time
time_fetch_fail_since_last_sync = 0

def get_time():
    time = utime.ticks_ms()  # Get current time in milliseconds
    # Convert to human readable format
    time = f"{time} ms"
    return time


def reset_e_inky():
    # Reset the e-ink display
    display.set_pen(15)  # Set pen to white
    display.clear()  # Clear the display
    display.update()  # Update the display to show changes
    display.set_pen(0)  # Set pen to black
    utime.sleep(1)  # Pause for a second


def load_wifi_json():
    try:
        with open("wifi.json", "r") as file:
            wifi_data = ujson.load(file)
            print(wifi_data)
            return wifi_data
    except OSError as e:
        print(f"Error reading wifi.json: {e}")
        return None


def connect_to_wifi(ssid, password):
    wlan = network.WLAN(network.STA_IF)  # Create a station interface
    wlan.active(True)  # Activate the interface
    wlan.connect(ssid, password)  # Connect to the WiFi network

    # Wait for connection
    timeout = 10  # Timeout in seconds
    start_time = utime.ticks_ms()
    while not wlan.isconnected():
        if utime.ticks_diff(utime.ticks_ms(), start_time) > timeout * 1000:
            print("Connection timed out")
            return False
        utime.sleep(1)  # Wait for a second before checking again

    print("Connected to WiFi")
    return True


def get_international_news():
    try:
        # Use BBC's RSS feed - lightweight and no API key needed
        response = urequests.get("http://feeds.bbci.co.uk/news/world/rss.xml")
        content = response.text

        # Simple parsing to extract the first headline
        # Find the first title tag after an item tag
        item_start = content.find("<item>")
        if item_start > -1:
            title_start = content.find("<title>", item_start) + 7
            title_end = content.find("</title>", title_start)
            headline = content[title_start:title_end]

            # Clean up any HTML/XML entities
            headline = headline.replace("&quot;", '"')
            headline = headline.replace("&amp;", "&")
            headline = headline.replace("&#39;", "'")
            headline = headline.replace("&lt;", "<")
            headline = headline.replace("<![", "")
            headline = headline.replace("CDATA[", "")
            headline = headline.replace("]]>", "")

            return headline
        else:
            return "No headlines found"

    except Exception as e:
        print(f"Error getting news: {e}")
        return "Failed to fetch news"


def display_headlines_with_wordwrap(headline, x_pos=10, y_start=10, max_width=140):
    # Word wrap logic for the headline
    words = headline.split()
    line = ""
    y_position = y_start

    for word in words:
        # Test if adding this word would make the line too long
        test_line = line + " " + word if line else word
        if (
            len(test_line) > max_width // (6)  # Approximate characters that fit in max_width
        ):  # Approximate characters that fit in max_width
            # Current line is full, print it and start a new line
            display.text(line, x_pos, y_position, scale=2)
            y_position += 15  # Smaller line spacing
            line = word  # Start new line with current word
        else:
            line = test_line

    # Print the last line of the headline
    if line:
        display.text(line, x_pos, y_position, scale=2)

    return y_position + 15  # Return the next available y position


# Add this function to sync with NTP servers
def get_time():
    global last_collected_time, time_fetch_fail_since_last_sync
    
    try:
        # WorldTimeAPI - provides time for London specifically
        response = urequests.get("http://worldtimeapi.org/api/timezone/Europe/London")
        time_data = response.json()
        response.close()
        
        # Extract time details
        datetime_str = time_data["datetime"]
        date_part = datetime_str.split("T")[0]
        time_part = datetime_str.split("T")[1].split(".")[0]
        
        year, month, day = [int(x) for x in date_part.split("-")]
        hour, minute, second = [int(x) for x in time_part.split(":")]
        
        # Convert API weekday (0=Sunday) to MicroPython RTC weekday (0=Monday)
        api_weekday = time_data.get("day_of_week", 0)
        mp_weekday = 6 if api_weekday == 0 else api_weekday - 1
        
        # Set the RTC
        rtc = RTC()
        rtc.datetime((year, month, day, mp_weekday, hour, minute, second, 0))
        
        # Save this successful time data
        last_collected_time = (year, month, day, mp_weekday, hour, minute, second)
        # Reset the failure counter
        time_fetch_fail_since_last_sync = 0
        
        print(f"Time synced via API: {year}-{month}-{day} {hour}:{minute}:{second}")
        return f"{hour:02d}:{minute:02d}"
        
    except Exception as e:
        print(f"API time sync failed: {e}")
        time_fetch_fail_since_last_sync += 1
        
        if last_collected_time:
            # We have a previously saved time, use it with adjustment
            year, month, day, weekday, hour, minute, second = last_collected_time
            
            # Add one minute for each failed attempt (adjust as needed)
            additional_minutes = time_fetch_fail_since_last_sync
            
            # Simple time calculation (not handling month/year boundaries)
            minute += additional_minutes
            hour += minute // 60
            minute %= 60
            day += hour // 24
            hour %= 24
            
            # Try to update RTC with our calculated time
            try:
                rtc = RTC()
                rtc.datetime((year, month, day, weekday, hour, minute, second, 0))
                print(f"Using calculated time: {hour:02d}:{minute:02d} (+{additional_minutes}min)")
                return f"{hour:02d}:{minute:02d}"
            except Exception as rtc_err:
                print(f"RTC update failed: {rtc_err}")
        
        # If all else fails, try to read current RTC
        try:
            rtc = RTC()
            dt = rtc.datetime()
            h, m = dt[4], dt[5]
            return f"{h:02d}:{m:02d}"
        except:
            return "??:??"
    

# Cronological run of main logic starts here


# Update the run function to use the new layout
def run():


    print("Starting main logic...")
    # Load WiFi configuration from JSON file
    wifi_config = load_wifi_json()
    if wifi_config:
        ssid = wifi_config.get("ssid", "Unknown SSID")
        password = wifi_config.get("password", "No Password")
        print(f"Loaded WiFi configuration: SSID={ssid}.\nEntering time loop...")
        # Connect to WiFi using the loaded configuration
        if connect_to_wifi(ssid, password):
            # Lets run the main logic every minute
            while True:
                print("Next iteration of time loop...")
                # Sync time if possible
                # Reset display and create layout with clock and headline
                reset_e_inky()
                #display.text("Top\nStory:", 10, 10, scale=3)
                headline = get_international_news()
                display_headlines_with_wordwrap(
                    headline, x_pos=5, y_start=5, max_width=160
                )

                # Now this will show the real time
                current_time = get_time()
                display.text(f"{current_time}", 105, 80, scale=7)
                display.update()
                utime.sleep(60)
                print("Main logic completed, waiting for next iteration...")
    else:
        print("Failed to load WiFi configuration. Exiting...")


run()  # Call the run function to execute the main logic
