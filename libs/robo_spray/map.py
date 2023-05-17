import json
from typing import List

from kivy.app import App
from kivy_garden.mapview import MapView, MapMarker
from kivy.uix.label import Label
from kivy.graphics import Color, Ellipse

from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout

import numpy as np

import os
dir_path = os.path.dirname(__file__)

class SparyMapMarker(MapMarker):
    def __init__(self, **kwargs):
        super(SparyMapMarker, self).__init__(**kwargs)
        
        # Customize marker properties
        self.size = (30, 30)  # Set the size of the marker (width, height)

    def add_instructions(self):
        # Override the add_instructions method to customize the marker shape
        with self.canvas:
            Color(0, 1, 0)  # Set the color of the marker
            Ellipse(pos=(self.x - self.size[0] / 2, self.y - self.size[1] / 2), size=self.size)

class CircleMarker(MapMarker):
    def __init__(self, lat, lon, radius, **kwargs):
        super(CircleMarker, self).__init__(lat=lat, lon=lon,radius=radius, **kwargs)
        self.radius = radius

    def add_canvas(self):
        with self.canvas:
            Color(*self.color)
            self.ellipse = Ellipse(pos=self.pos, size=(self.radius * 2, self.radius * 2))

    def update_canvas(self):
        self.ellipse.pos = self.pos
        self.ellipse.size = (self.radius * 2, self.radius * 2)


def marker_function():
    print("Hey")

def draw_tracks(mapview:MapView, data:dict) -> None:

    marker_path = os.path.join(dir_path,"../../src/assets/path_marker.png")
    # Add markers to the MapView 
    for feature in data['features']:
        coordinates = feature['geometry']['coordinates']
        marker = MapMarker(lat=coordinates[1], lon=coordinates[0],source=marker_path,size=(50,50))
        #marker = MapMarker(lat=coordinates[1], lon=coordinates[0])
        #marker.add_widget(Label(text=feature["properties"]["Name"]))
        #marker.add_widget(Button(text=feature["properties"]["Name"]))
       
        # mapview.add_marker(marker)
        mapview.add_widget(marker)

def draw_markers(mapview:MapView, data:dict) -> List[MapMarker]:

    markers = []
    
    # Add markers to the MapView 
    for feature in data['features']:
        coordinates = feature['geometry']['coordinates']

        condition = feature["properties"]["condition"]

        marker_path = os.path.join(dir_path,f"../../src/assets/{condition}.png")        
        marker = MapMarker(lat=coordinates[1], lon=coordinates[0],
                           source=marker_path)
        #marker = MapMarker(lat=coordinates[1], lon=coordinates[0])
        #marker.add_widget(Label(text=feature["properties"]["Name"]))
        #marker.add_widget(Button(text=feature["properties"]["Name"]))
       
        # mapview.add_marker(marker)
        mapview.add_widget(marker)

        markers.append(marker)

    return markers

def remove_markers(mapview:MapView,markers:List[MapMarker]) -> None:
    for marker in markers:
        mapview.remove_marker(marker)




class CustomMarkerButton(FloatLayout):
    def __init__(self, marker, **kwargs):
        super(CustomMarkerButton, self).__init__(**kwargs)
        
        self.marker = marker
        
        # Create a button widget
        self.button = Button(text='Marker', size_hint=(0.5, 0.5), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        self.button.bind(on_release=self.on_button_release)
        
        # Create a label widget
        self.label = Label(text='Custom Marker', size_hint=(0.5, 0.5), pos_hint={'center_x': 0.5, 'center_y': 0.7})
        
        # Add the button and label to the layout
        self.add_widget(self.button)
        self.add_widget(self.label)
        
        # Add the layout to the marker
        self.marker.add_widget(self)

    def on_button_release(self, *args):
        print("Button pressed!")

# test app
if __name__ == "__main__":
    class CustomMapApp(App):
        def build(self):
            mapview = MapView(zoom=10, lat=0, lon=0)
            
            # Create custom map markers and add them to the MapView
            marker1 = SparyMapMarker(lat=0, lon=0)
            mapview.add_marker(marker1)
            
            marker2 = SparyMapMarker(lat=1, lon=1)
            mapview.add_marker(marker2)
            
            return mapview
        
    CustomMapApp().run()

