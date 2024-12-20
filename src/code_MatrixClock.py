"""
MatrixClock - a HUB75 LED matrix clock driven by Adafruit's MaxtrixPortal M4.

* Synchronization with NTP.
* Temperature/humidity ambient sensor (Sensirion SHT40).

@author: mada
@version: 2024-12-18
"""

import sys
import os
import time

## Network ---------------------------------------------------------------------
import board
import digitalio
import busio
from adafruit_esp32spi import adafruit_esp32spi

import neopixel
from adafruit_esp32spi import adafruit_esp32spi_wifimanager

import adafruit_connection_manager

## NTP & RTC -------------------------------------------------------------------
from rtc import RTC
from adafruit_ntp import NTP

## Display ---------------------------------------------------------------------
from adafruit_matrixportal.matrix import Matrix
from adafruit_display_text.label import Label
from adafruit_bitmap_font import bitmap_font
import adafruit_imageload
import displayio
import terminalio

## Clock -----------------------------------------------------------------------
from datetime_util import cettime


##******************************************************************************
##******************************************************************************

## DEBUG mode
DEBUG = False
# DEBUG = True
## Blinking colon
BLINK = True
## NTP sync interval
NTP_INTERVAL = 3600 * 12  # 3600s = 60min = 1h
## Last NTP sync
ts_lastntpsync = 0
## Clock counter
if DEBUG:
    ## Start at 05:59:00 UTC = 06:59:00 CET ...
    ts_clocktick = 60 * 60 * 5 + 59 * 60
else:
    ## Start at 00:00:00 UTC
    ts_clocktick = time.time()

##******************************************************************************
##******************************************************************************


##==============================================================================
print("\n****************************")
print(  "**** Settings & Secrets ****")
print(  "****************************")

## Read credentials and more from a settings.toml file
settings = {
    "CIRCUITPY_WIFI_SSID": os.getenv("CIRCUITPY_WIFI_SSID"),
    "CIRCUITPY_WIFI_PASSWORD": os.getenv("CIRCUITPY_WIFI_PASSWORD"),
    # "TIMEZONE": getenv("TIMEZONE"),
    # "NTP_INTERVAL": getenv("NTP_INTERVAL"),
    }
CIRCUITPY_WIFI_SSID = settings["CIRCUITPY_WIFI_SSID"]
CIRCUITPY_WIFI_PASSWORD = settings["CIRCUITPY_WIFI_PASSWORD"]


##==============================================================================
print("\n***********************")
print(  "**** Network Setup ****")
print(  "***********************")

esp32_cs = digitalio.DigitalInOut(board.ESP_CS)
esp32_busy = digitalio.DigitalInOut(board.ESP_BUSY)
esp32_reset = digitalio.DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)

esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_busy, esp32_reset)

if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
    print("## ESP32 found and in idle mode")
print("## Firmware vers.", esp.firmware_version)
print("## MAC addr:", ":".join("%02X" % byte for byte in esp.MAC_address))
print("## IP addr:", esp.pretty_ip(esp.ip_address))

## Scan networks (=> slow !!!)
# for ap in esp.scan_networks():
#     print("\t%-23s RSSI: %d" % (ap.ssid, ap.rssi))

print(">> Connecting...")
while not esp.is_connected:
    try:
        esp.connect_AP(CIRCUITPY_WIFI_SSID, CIRCUITPY_WIFI_PASSWORD)
    except OSError as e:
        print("!! Could not connect, retrying: ", e)
        continue
print("## Connected to", esp.ap_info.ssid, "\tRSSI:", esp.ap_info.rssi, "\tIP addr:", esp.pretty_ip(esp.ip_address))


##==============================================================================
print("\n*******************")
print(  "**** NTP & RTC ****")
print(  "*******************")

pool = adafruit_connection_manager.get_radio_socketpool(esp)
ntp = NTP(pool, tz_offset=0, cache_seconds=3600, server="pool.ntp.org")
print("## Current NTP time:", ntp.datetime)
rtc = RTC()
rtc.datetime = ntp.datetime
print("## Current RTC time:", rtc.datetime)


##==============================================================================
print("\n***********************")
print(  "**** Display Setup ****")
print(  "***********************")

matrix = Matrix(
    # width=64, height=32,
    # rotation=180,
    )
time.sleep(1)  # show the Adafruit logo for 1 second
display = matrix.display

## Load Python logo from a BMP file
image, palette = adafruit_imageload.load("Python-logo_64x32.bmp")
tile_grid = displayio.TileGrid(image, pixel_shader=palette)
group = displayio.Group()
group.append(tile_grid)
display.root_group = group
time.sleep(2)  # show the Python logo for 2 seconds

# text = "Hello\nred!"
# text_area = Label(terminalio.FONT, text=text, color=0x440000)
# text_area.x = 1
# text_area.y = 8
# display.root_group = text_area
# time.sleep(1)  # show the text for 1 second

# text = "Hello\ngreen!"
# text_area = Label(terminalio.FONT, text=text, color=0x004400)
# text_area.x = 28
# text_area.y = 8
# display.root_group = text_area
# time.sleep(1)  # show the text for 1 second

## Create a color palette
color = displayio.Palette(5)
color[0] = 0x000000  # black background
color[1] = 0x400000  # red
color[2] = 0xCC4000  # amber
color[3] = 0x404000  # greenish
color[4] = 0x0846e4  # blueish

# ## Create a bitmap object (width, height, bit depth)
# bitmap = displayio.Bitmap(64, 32, 5)
# ## Set all pixels to black
# for i in range(64):
#     for j in range(32):
#         bitmap[i, j] = 0

# ## Draw a blueish crosshair in the middle
# for i in range(64):
#     bitmap[i, 15] = 4
# for j in range(32):
#     bitmap[32, j] = 4

# ## Create a Group
# group = displayio.Group()
# ## Create a TileGrid using the Bitmap and Palette
# tile_grid = displayio.TileGrid(bitmap, pixel_shader=color)
# ## Add the TileGrid to the Group
# group.append(tile_grid)
# display.root_group = group
# time.sleep(2)  # show the blueish line for 1 second


##==============================================================================
print("\n*********************************************")
print(  "**** SHT40 Temperature & Pressure Sensor ****")
print(  "*********************************************")

## To use default I2C bus (most boards)
i2c_bus = board.I2C()  # uses board.SCL and board.SDA
# i2c_bus = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

while not i2c_bus.try_lock():
    pass
try:
    i2c_devices = i2c_bus.scan()
    print("\n## I2C device addresses found:")
    print([(device_address, hex(device_address)) for device_address in i2c_devices])
finally:
    i2c_bus.unlock()

sht40_sensor = 0x44  # i2c_devices[1]

sht40_modes = (
    ("SERIAL_NUMBER", 0x89, "Serial number", 0.01),
    ("NOHEAT_HIGHPRECISION", 0xFD, "No heater, high precision", 0.01),
    ("NOHEAT_MEDPRECISION", 0xF6, "No heater, med precision", 0.005),
    ("NOHEAT_LOWPRECISION", 0xE0, "No heater, low precision", 0.002),
    ("HIGHHEAT_1S", 0x39, "High heat, 1 second", 1.1),
    ("HIGHHEAT_100MS", 0x32, "High heat, 0.1 second", 0.11),
    ("MEDHEAT_1S", 0x2F, "Med heat, 1 second", 1.1),
    ("MEDHEAT_100MS", 0x24, "Med heat, 0.1 second", 0.11),
    ("LOWHEAT_1S", 0x1E, "Low heat, 1 second", 1.1),
    ("LOWHEAT_100MS", 0x15, "Low heat, 0.1 second", 0.11),
    )


##------------------------------------------------------------------------------
def read_sensor():
    '''
    Read measurement data from Sensirion SHT40.

    Returns
    -------
    * t_degC : float
    * rh_pRH : float
    '''
    mode = sht40_modes[1]  # NOHEAT_HIGHPRECISION
    while not i2c_bus.try_lock():
        pass
    try:
        # print ("\n## Reading sensor data...")
        i2c_bus.writeto(sht40_sensor, bytearray([mode[1]]))
        time.sleep(mode[-1])
        rx_bytes = bytearray(6)
        i2c_bus.readfrom_into(sht40_sensor, rx_bytes)
        # print('>', rx_bytes, len(rx_bytes))
        t_ticks = rx_bytes[0] * 256 + rx_bytes[1]
        rh_ticks = rx_bytes[3] * 256 + rx_bytes[4]
        t_degC = -45 + 175 * t_ticks / 65535  # 2^16 - 1 = 65535
        rh_pRH = -6 + 125 * rh_ticks / 65535
        if (rh_pRH > 100):
            rh_pRH = 100
        if (rh_pRH < 0):
            rh_pRH = 0
        # print('> temperature:', t_degC)
        # print('> humidity:', rh_pRH)

        return t_degC, rh_pRH

    finally:
        i2c_bus.unlock()

print("\n## Reading sensor data...")
t_degC, rh_pRH = read_sensor()
print('> temperature:', t_degC)
print('> humidity:', rh_pRH)


##==============================================================================
print("\n**********************")
print(  "**** Matrix Clock ****")
print(  "**********************")

## Define fonts
font_large = bitmap_font.load_font("IBMPlexMono-Medium-24_jep.bdf")
# font_small = terminalio.FONT
# font_small = bitmap_font.load_font("6x10.bdf")
font_small = bitmap_font.load_font("helvR10.bdf")

## Create labels for the display text
clock_label = Label(font_large)
sensor_label = Label(font_small)

## Place the labels
clock_label.y = display.height // 3
sensor_label.y = 26

## Create a display group for the labels
group = displayio.Group()
display.root_group = group
## Add the labels to the group
group.append(clock_label)
group.append(sensor_label)


##------------------------------------------------------------------------------
def update_time(*, hours=None, minutes=None, show_colon=False):
    """
    Update the clock label with the current time."""
    # now = time.localtime()
    now = cettime(time.time())
    if hours is None:
        hours = now[3]
    if hours >= 20 or hours < 7:
        ## Evening hours to morning
        clock_label.color = color[1]
        sensor_label.color = color[1]
    else:
        ## Daylight hours
        clock_label.color = color[3]
        sensor_label.color = color[3]

    if minutes is None:
        minutes = now[4]

    seconds = now[5]

    if BLINK:
        colon = ":" if show_colon or seconds % 2 else " "
    else:
        colon = ":"

    time_str_display = "{:d}{}{:02d}".format(hours, colon, minutes)
    time_str_stdout = "{}:{:02d}".format(time_str_display, seconds)
    clock_label.text = time_str_display
    bbx, bby, bbwidth, bbh = clock_label.bounding_box

    ## Place the label
    clock_label.x = round(display.width / 2 - bbwidth / 2)  # centered
    clock_label.y = display.height // 3
    if DEBUG:
        print("## clock_label bounding box: {},{},{},{}".format(bbx, bby, bbwidth, bbh))
        print("## clock_label x: {} y: {}".format(clock_label.x, clock_label.y))

    ## Read temperature and humidity
    t_degC, rh_pRH = read_sensor()
    sensor_str = "{:.1f}°  {:.1f}%".format(t_degC, rh_pRH)
    sensor_label.text = sensor_str
    bbx, bby, bbwidth, bbh = sensor_label.bounding_box
    sensor_label.x = round(display.width / 2 - bbwidth / 2)  # centered
    sensor_label.y = 26
    if DEBUG:
        print("## sensor_label bounding box: {},{},{},{}".format(bbx, bby, bbwidth, bbh))
        print("## sensor_label x: {} y: {}".format(sensor_label.x, sensor_label.y))

    print("Tick: {} - {}".format(time_str_stdout, sensor_str))


##******************************************************************************
##******************************************************************************
update_time(show_colon=True)  # display whatever time is on the board
while True:
    if ts_lastntpsync is None or time.monotonic() > ts_lastntpsync + NTP_INTERVAL:
        print(">> Updating time via NTP...")
        try:
            update_time(show_colon=True)  # make sure a colon is displayed while updating
            rtc.datetime = ntp.datetime
            ts_lastntpsync = time.monotonic()
        except RuntimeError as e:
            print("!! Some error occured, retrying! -", e)
    update_time()
    time.sleep(1)
