from picographics import PicoGraphics, DISPLAY_INKY_PACK
import utime
# Lets connect to the internert and g
import ujson
import network
import urequests

# Global variables
# Initialize the display - specify a compatible pen type
display = PicoGraphics(display=DISPLAY_INKY_PACK)

# Draw some basic text with proper parameters
display.set_pen(0)  # Set pen to black
# Pause for a second

def get_time():
    time= utime.ticks_ms()  # Get current time in milliseconds
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
        with open('wifi.json', 'r') as file:
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
            headline = headline.replace("&quot;", "\"")
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

def display_headlines():
    reset_e_inky()
    display.text("Today's Top Story:", 10, 10, scale=2)
    
    # Add parentheses to call the function
    headline = get_international_news()
    y_position = 45  # Start position for the headline
    
    # Word wrap logic for the headline
    words = headline.split()
    line = ""
    
    for word in words:
        # Test if adding this word would make the line too long
        test_line = line + " " + word if line else word
        if len(test_line) > 30:  # Character limit per line
            # Current line is full, print it and start a new line
            display.text(line, 10, y_position, scale=1)
            y_position += 15  # Smaller line spacing
            line = word  # Start new line with current word
        else:
            line = test_line
    
    # Print the last line of the headline
    if line:
        display.text(line, 10, y_position, scale=1)
    
    display.update()
# Cronological run of main logic starts here

def run():
    #reset_e_inky()
    #display.text(f"Boot successful in: {get_time()}", 10, 20, scale=2)  # Draw text at position (10, 20) with scale 2
    # Update the display
    #display.update()
    # Pause for a second
    #utime.sleep(1)

    # Load WiFi configuration from JSON file
    wifi_config = load_wifi_json()
    if wifi_config:
        ssid = wifi_config.get('ssid', 'Unknown SSID')
        password = wifi_config.get('password', 'No Password')
        display.text(f"SSID: {ssid}", 10, 60, scale=2)
        display.text(f"Password: {password}", 10, 100, scale=2)
        # Update the display again
        display.update()
        # Pause for a second    
        utime.sleep(1)
    # Connect to WiFi using the loaded configuration
    if connect_to_wifi(ssid, password):
        #reset_e_inky()
        #display.text("Connected to WiFi", 10, 60, scale=2)
        #display.update()

        display_headlines()
run()  # Call the run function to execute the main logic