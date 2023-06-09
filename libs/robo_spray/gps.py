import time
import serial
import struct
from ublox_gps import UbloxGps
from ublox_gps import sparkfun_predefines as sp
from multiprocessing import Process,Queue
import piexif
#import cv2
from fractions import Fraction

import datetime
import json

import glob
import subprocess
import os

assets_path = os.path.join(os.path.dirname(__file__),"../../src/assets/")

def convert_to_dms(degrees):
    """
    Convert decimal degrees to degrees, minutes, and seconds format.
    """
    # Get the degrees, minutes, and seconds
    d = int(degrees)
    m = int((degrees - d) * 60)
    s = round(((degrees - d - m/60) * 3600), 2)
    
    # Return the DMS format
    return (d, m, s)


def to_deg(value, loc):
    """convert decimal coordinates into degrees, munutes and seconds tuple
    Keyword arguments: value is float gps-value, loc is direction list ["S", "N"] or ["W", "E"]
    return: tuple like (25, 13, 48.343 ,'N')
    """
    if value < 0:
      loc_value = loc[0]
    elif value > 0:
      loc_value = loc[1]
    else:
      loc_value = ""
    abs_value = abs(value)
    deg = int(abs_value)
    t1 = (abs_value - deg) * 60
    min = int(t1)
    sec = round((t1 - min) * 60, 5)
    return (deg, min, sec, loc_value)

def change_to_rational(number):
    """convert a number to rantional
    Keyword arguments: number
    return: tuple like (1, 2), (numerator, denominator)
    """
    f = Fraction(str(number))
    return (f.numerator, f.denominator)

def geotag_image(img,lat,lon, save_path):

    #exif_latitude = convert_to_dms(lat)
    #exif_longitude = convert_to_dms(lon)

    exif_latitude = piexif.GPSIFD.GPSLatitude.convert(lat)
    exif_latitude_ref = 'N' if lat[0] > 0 else 'S'
    exif_longitude = piexif.GPSIFD.GPSLongitude.convert(lon)
    exif_longitude_ref = 'E' if lon[0] > 0 else 'W'

    # Create the EXIF data dictionary
    exif_dict = {"GPS": {
        piexif.GPSIFD.GPSLatitudeRef: exif_latitude_ref,
        piexif.GPSIFD.GPSLatitude: exif_latitude,
        piexif.GPSIFD.GPSLongitudeRef: exif_longitude_ref,
        piexif.GPSIFD.GPSLongitude: exif_longitude,
    }}

    # Convert the EXIF data dictionary to bytes
    exif_bytes = piexif.dump(exif_dict)

    # Add the EXIF data to the image
    cv2.imwrite(save_path, img, [int(cv2.IMWRITE_JPEG_QUALITY), 95, int(cv2.IMWRITE_JPEG_EXIF_QTABLES), 1, int(cv2.IMWRITE_JPEG_EXIF_THUMBNAIL), 1, int(cv2.IMWRITE_JPEG_EXIF_SIZE), len(exif_bytes), int(cv2.IMWRITE_JPEG_EXIF_DATA), exif_bytes])


def set_gps_location(file_name, lat, lng, altitude, gpsTime):
    """Adds GPS position as EXIF metadata
    Keyword arguments:
    file_name -- image file
    lat -- latitude (as float)
    lng -- longitude (as float)
    altitude -- altitude (as float)
    """
    lat_deg = to_deg(lat, ["S", "N"])
    lng_deg = to_deg(lng, ["W", "E"])

    exiv_lat = (change_to_rational(lat_deg[0]), change_to_rational(lat_deg[1]), change_to_rational(lat_deg[2]))
    exiv_lng = (change_to_rational(lng_deg[0]), change_to_rational(lng_deg[1]), change_to_rational(lng_deg[2]))

    gps_ifd = {
      piexif.GPSIFD.GPSVersionID: (2, 0, 0, 0),
      piexif.GPSIFD.GPSAltitudeRef: 0,
      piexif.GPSIFD.GPSAltitude: change_to_rational(round(altitude)),
      piexif.GPSIFD.GPSLatitudeRef: lat_deg[3],
      piexif.GPSIFD.GPSLatitude: exiv_lat,
      piexif.GPSIFD.GPSLongitudeRef: lng_deg[3],
      piexif.GPSIFD.GPSLongitude: exiv_lng,
      piexif.GPSIFD.GPSDateStamp: gpsTime
    }

    exif_dict = {"GPS": gps_ifd}
    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, file_name)

class ObjectFromDict:
    def __init__(self, **entries):
        self.__dict__.update(entries)

def get_product_attribute(device_path):
    command = ['udevadm', 'info', '-q', 'all', '-a', '-n', device_path]
    output = subprocess.check_output(command, universal_newlines=True)
    lines = output.splitlines()
    for line in lines:
        line = line.strip()
        if line.startswith('ATTRS{product}'):
            product = line.strip().split('==')[-1]
            return product
    return None

def find_gps_device(gps_product="u-blox"):
    devices = glob.glob('/dev/ttyACM*')
    for device in devices:
        
        try:
           product = get_product_attribute(device_path=device) 
           if gps_product in product:
                print(f"Found {product} on {device}")
                return device
        except IOError:
            pass

    return None

class GPS:
    def __init__(self,update_ms=300,simulation=False):
        try:
            device = find_gps_device()
            self.gps_port = serial.Serial(device, baudrate=38400, timeout=1)
            self.gps = UbloxGps(self.gps_port)
        except Exception as e:
            print(e)
            self.gps_port = None
            self.gps = None

        if self.gps:
            # Setup samping rate
            ubx_id = 0x08
            ubx_payload = struct.pack("<HHH", update_ms, 1, 0)
            # Send the UBX-CFG-RATE message
            self.gps.send_message(sp.CFG_CLS, ubx_id, ubx_payload)

        self.simulation = simulation
        self.queue:Queue = Queue() # FIFO Queue
        self.running = False

        self.geo:object = None

        # Dry run
        if 0:
            self.update_gps()
            _ = self.get_gps_data()

    def start(self):
        self.process = Process(target=self._run, args=())
        self.running = True 
        self.process.start()
    
    def _run(self):
        if self.gps == None or self.simulation:
            print("GPS module not detected. Verify the connection.")
            print("Running GPS simulation mode")
            
            # Runing GPS Simulation
            with open(os.path.join(assets_path,'spray_position_all.json')) as file:
                data = json.load(file)
                    # Add markers to the MapView 
            sorted_features = sorted(data['features'], key=lambda feature: feature['properties']['name'])

            sorted_data = {
                'type': 'FeatureCollection',
                'features': sorted_features
            }

            gps_data_len = len(sorted_data['features'])
            idx = 0
            while self.running:
                # Get the current time
                current_time = datetime.datetime.now()
                coordinates = sorted_data['features'][idx]['geometry']['coordinates']
                geo_dict = {
                            "year":current_time.year,
                            "month":current_time.month,
                            "day":current_time.day,
                            "hour":current_time.hour,
                            "min":current_time.min,
                            "sec":current_time.second,
                            "nano":current_time.microsecond*1000,
                            "lon":coordinates[0],
                            "lat":coordinates[1],
                            "height": 0,
                            "headMot":0,
                } 


                try:
                    self.queue.put(ObjectFromDict(**geo_dict),timeout=0)
                except Exception as e:
                    print("GPS queue is full")
                    print(e)

                idx += 1
                # Reset
                if idx == gps_data_len:
                    print("Reset idx")
                    idx = 0
                time.sleep(0.10)

        while self.running:
            self.update_gps()
            time.sleep(0.01)

    def update_gps(self):
        try:
            geo_response = self.gps.geo_coords()
        except Exception as e:
            print(e)
            geo_response = None

        if geo_response:
            if 0:
                print("UTC Time {}:{}:{}".format(geo_response.hour, geo_response.min,geo_response.sec))
                print("Longitude: ", geo_response.lon) 
                print("Latitude: ", geo_response.lat)
                print("Heading of Motion: ", geo_response.headMot)

            geo_dict = {
                        "year":geo_response.year,
                        "month":geo_response.month,
                        "day":geo_response.day,
                        "hour":geo_response.hour,
                        "min":geo_response.min,
                        "sec":geo_response.sec,
                        "nano":geo_response.nano,
                        "lon":geo_response.lon,
                        "lat":geo_response.lat,
                        "height": geo_response.height,
                        "headMot":geo_response.headMot,
            }

            try:
                self.queue.put(ObjectFromDict(**geo_dict),timeout=0)
            except Exception as e:
                print("GPS queue is full")
                print(e)

    def get_gps_data(self):
        #@TODO: Add EKF here. Aggrgate all the previous GPS data points
        
        # Get all gps points from the queue
        while not self.queue.empty():
            # print(self.queue.qsize())
            self.geo = self.queue.get()
            # print("UTC Time {}:{}:{}".format(self.geo.hour, self.geo.min,self.geo.sec))


        return self.geo
    
    def stop(self):
        self.running = False
        self.process.kill()

if __name__ == "__main__":

    # Usage
    gps_device = find_gps_device()
    if gps_device:
        print(f"GPS device found: {gps_device}")
    else:
        print("No GPS device found.")
        
    gps = GPS()
    gps.start()
    try: 
        while True:
            time.sleep(0.3)
            gps_data = gps.get_gps_data()
            if 1:
                if gps_data is not None:
                    print("UTC Time {}:{}:{}".format(gps_data.hour, gps_data.min,gps_data.sec))
                    print("Longitude: ", gps_data.lon) 
                    print("Latitude: ", gps_data.lat)
                    print("Heading of Motion: ", gps_data.headMot)
    except KeyboardInterrupt:
        gps.stop()


