from picographics import PicoGraphics, DISPLAY_INKY_PACK
import utime
import network
import urequests
import ujson
from machine import RTC

# Global variables
# Initialize the display - specify a compatible pen type
display = PicoGraphics(display=DISPLAY_INKY_PACK)

# Draw some basic text with proper parameters
display.set_pen(0)  # Set pen to black

# Global variables for caching and timing
last_time_sync = 0  # Last time we synced with time server (in seconds)
time_fetch_fail_since_last_sync = 0  # Count of failed time fetches since last sync
last_news_fetch = 0  # Last time we fetched news (in seconds)
cached_headlines = []  # Store multiple headlines
current_headline_index = 0  # Which headline we're currently displaying
last_weather_fetch = 0  # Last time we fetched weather data
cached_weather = None  # Store weather information

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

def get_weather():
    """Fetches weather data for London from Open-Meteo"""
    global last_weather_fetch, cached_weather
    
    current_time = utime.time()
    # Only fetch if we have no data or it's been 10+ minutes
    if cached_weather is None or (current_time - last_weather_fetch) > 600:  # 600 seconds = 10 minutes
        try:
            print("Fetching weather data...")
            # TODO smarter coordinates
            latitude = "52.048326"
            longitude = "-0.024102"
            url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m,wind_speed_10m,weather_code&timezone=Europe/London"
            
            response = urequests.get(url)
            weather_data = response.json()
            response.close()
            
            # Extract current weather
            current = weather_data.get("current", {})
            temperature = current.get("temperature_2m", "?")
            wind_speed = current.get("wind_speed_10m", "?")
            weather_code = current.get("weather_code", 0)
            
            # Create weather description based on WMO weather code
            weather_desc = get_weather_description(weather_code)
            
            # Cache the data
            cached_weather = {
                "temp": temperature,
                "wind": wind_speed,
                "desc": weather_desc
            }
            last_weather_fetch = current_time
            
            print(f"Weather: {temperature}°C, {wind_speed} km/h, {weather_desc}")
        except Exception as e:
            print(f"Weather API error: {e}")
            if cached_weather is None:  # Only use placeholder if we have no data
                cached_weather = {"temp": "?", "wind": "?", "desc": "Unknown"}
    
    return cached_weather

def get_weather_description(code):
    """Convert WMO weather code to simple description"""
    if code < 10:  # Clear or mostly clear
        return "Clear"
    elif code < 20:  # Fog
        return "Foggy"
    elif code < 30:  # Drizzle
        return "Drizzle"
    elif code < 40:  # Rain
        return "Rain"
    elif code < 50:  # Snow
        return "Snow"
    elif code < 60:  # Rain showers
        return "Showers"
    elif code < 70:  # Snow showers
        return "Snow"
    elif code < 80:  # Thunderstorm
        return "Thunder"
    elif code < 100:  # Rain/snow with thunder
        return "Storms"
    else:
        return "Unknown"


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


def fetch_multiple_headlines(count=10):
    """Fetches multiple headlines from BBC RSS feed"""
    headlines = []
    try:
        # Use BBC's RSS feed
        response = urequests.get("http://feeds.bbci.co.uk/news/world/rss.xml")
        content = response.text
        response.close()

        # Find multiple headlines
        start_pos = 0
        for _ in range(count):
            item_start = content.find("<item>", start_pos)
            if item_start == -1:
                break

            title_start = content.find("<title>", item_start) + 7
            title_end = content.find("</title>", title_start)
            headline = content[title_start:title_end]

            # Clean up HTML entities
            headline = headline.replace("&quot;", '"')
            headline = headline.replace("&amp;", "&")
            headline = headline.replace("&#39;", "'")
            headline = headline.replace("&lt;", "<")
            headline = headline.replace("<![", "")
            headline = headline.replace("CDATA[", "")
            headline = headline.replace("]]>", "")

            headlines.append(headline)
            start_pos = title_end

        print(f"Fetched {len(headlines)} headlines")
        return headlines
    except Exception as e:
        print(f"Error fetching headlines: {e}")
        return ["Failed to fetch news"]


def get_next_headline():
    """Gets the next headline from cache or fetches new ones if needed"""
    global cached_headlines, current_headline_index, last_news_fetch

    current_time = utime.time()

    # Check if we need to fetch new headlines (every 30 minutes)
    if (
        not cached_headlines or (current_time - last_news_fetch) > 1800
    ):  # 1800 seconds = 30 minutes
        cached_headlines = fetch_multiple_headlines()
        last_news_fetch = current_time
        current_headline_index = 0

    # No headlines available
    if not cached_headlines:
        return "No headlines available"

    # Get current headline and advance index for next time
    headline = cached_headlines[current_headline_index]
    current_headline_index = (current_headline_index + 1) % len(cached_headlines)

    return headline


def display_headlines_with_wordwrap(headline, x_pos=10, y_start=10, max_width=140):
    # Word wrap logic for the headline
    words = headline.split()
    line = ""
    y_position = y_start

    for word in words:
        # Test if adding this word would make the line too long
        test_line = line + " " + word if line else word
        if len(test_line) > max_width // (
            6
        ):  # Approximate characters that fit in max_width  # Approximate characters that fit in max_width
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
def get_time(force_sync=False):
    global last_collected_time, time_fetch_fail_since_last_sync, last_time_sync

    current_time = utime.time()
    # Only sync if it's been 5+ minutes or we're forced to sync
    if force_sync or (current_time - last_time_sync) > 300:  # 300 seconds = 5 minutes
        try:
            print("Syncing time with API...")
            # WorldTimeAPI - provides time for London specifically
            response = urequests.get(
                "http://worldtimeapi.org/api/timezone/Europe/London"
            )
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
            last_time_sync = current_time

            print(f"Time synced via API: {year}-{month}-{day} {hour}:{minute}:{second}")
        except Exception as e:
            print(f"API time sync failed: {e}")
            time_fetch_fail_since_last_sync += 1

    # Always read current time from RTC
    try:
        rtc = RTC()
        dt = rtc.datetime()
        h, m = dt[4], dt[5]
        return f"{h:02d}:{m:02d}"
    except:
        return "??:??"


# Cronological run of main logic starts here


# Update the run function with our optimized approach
def run():
    print("Starting main logic...")
    # Load WiFi configuration from JSON file
    wifi_config = load_wifi_json()
    if wifi_config:
        ssid = wifi_config.get("ssid", "Unknown SSID")
        password = wifi_config.get("password", "No Password")

        # Connect to WiFi using the loaded configuration
        if connect_to_wifi(ssid, password):
            print("Entering main loop...")
            while True:
                print("Syncing from APIs")
                # Force sync time on first run
                get_time(force_sync=True)

                # Fetch initial headlines
                fetch_multiple_headlines()  # This will populate the cache
                print("Headlines cached.")

                # Fetch initial data
                fetch_multiple_headlines()  # Headlines
                get_weather()  # Weather

                print("Updating display...")

                

                # Now lets loop 10 times before the next API call
                for _ in range(10):
                    # Reset display
                    reset_e_inky()

                    # Get next headline from cache
                    headline = get_next_headline()
                    display_headlines_with_wordwrap(
                        headline, x_pos=5, y_start=5, max_width=160
                    )

                    # Get current time (syncs every 5 min)
                    current_time = get_time()
                    display.text(f"{current_time}", 120, 80, scale=7)
                    
                    # Add weather information at the bottom
                    weather = get_weather()
                    weather_text = f"{weather['temp']}°C\n{weather['desc']}"
                    display.text(weather_text, 10, 100, scale=2)

                    # Update display
                    display.update()

                    # Wait for next update
                    print("Waiting for next minute...")
                    utime.sleep(60)
                    print("Minute passed, updating...")
                print("10 minute cycle completed, fetching new headlines and resyncing time...")
    else:
        print("Failed to load WiFi configuration. Exiting...")


run()  # Call the run function to execute the main logic
