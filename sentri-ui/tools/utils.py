import os
from textwrap import dedent
from agno.agent import Agent
from agno.models.google import Gemini
import json
import logging
import requests
from typing import List, Optional, Dict, Any
from pathlib import Path
import math
import io

import openmeteo_requests
import requests_cache
from retry_requests import retry
import pandas as pd
import datetime

from tools.payload import (get_payload_of_create_program_api,
                           get_payload_of_list_programs_irrigation_envents_api,
                           get_payload_for_create_irrigation_event_api,
                           get_list_area_by_mission_api,
                           get_payload_for_controllers_api)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EARTH_RADIUS_M = 6_371_000.0
METERS_PER_DEGREE_LAT = 111_320.0
DEFAULT_MISSION_DIR = Path("./tools/tool_management/building_detection/missions")
HOVER_TOLERANCE = 0.3
MAP_TILE_LAYER = os.getenv("GOOGLE_MAP_LAYER", "s")

takeoff_position: Optional[List[float]] = None
drone_ready = False
drone_armed = False
ai_control_active = False
running = True
takeoff_geodetic: Optional[Dict[str, float]] = None

class APIHandler:
    """
    Class to handle API requests and responses for Mimosatek.
    """

    def __init__(self):
        # Skip authentication for new Sentri project
        self.token = None
        self.url = os.getenv("API_URL", "")
        self.headers = {
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'en-US,en;q=0.9,vi;q=0.8',
            'Content-Type': 'application/json'
        }
        if self.token:
            self.headers['authorization'] = self.token

    def get_authen_token(self) -> str:
            """
            Function to get the authentication token from the Mimosatek API.
            """
            url = "https://demo.mimosatek.com/api/auth"

            payload = {
                "query": """
                    mutation login ($username: String!, $password: String!) {
                        login(username: $username, password: $password, long_lived: true) {
                            token
                        }
                    }
                """,
                "variables": {
                    "username": "phonglab@mimosatek.com",
                    "password": "mimosatek"
                }
            }

            headers = {
                'accept': '*/*',
                'accept-encoding': 'gzip, deflate, br',
                'accept-language': 'en-US,en;q=0.9,vi;q=0.8',
                'Content-Type': 'application/json'
            }

            try:
                response = requests.post(url, headers=headers, json=payload)
                response.raise_for_status()  # Raise an exception for bad status codes
                
                response_data = response.json()
                
                if "data" in response_data and "login" in response_data["data"]:
                    return response_data["data"]["login"]["token"]
                else:
                    raise ValueError("Invalid response format or login failed")
                
            except requests.exceptions.RequestException as e:
                raise Exception(f"Request failed: {e}")
            except (KeyError, ValueError) as e:
                raise Exception(f"Failed to extract token from response: {e}")
            
    # @staticmethod
    # def get_controller_id_by_mission_and_area_id(mission_id: str, area_id: str) -> Dict[str, Any]:
    #     """
    #     Get the controller ID based on mission and area IDs.
        
    #     Args:
    #         mission_id (str): The ID of the mission.
    #         area_id (str): The ID of the area.
        
    #     Returns:
    #         str: The controller ID.
    #     """

    #     #TODO: Implement the logic to retrieve the controller ID based on mission and area IDs.
    #     try:
    #         return {
    #             "mission_id": mission_id,
    #             "area_id": area_id,
    #             "controller_id": "4034b240-6fc1-11ed-9cbe-f9420b7f5b37"  # Replace with actual logic to get controller ID
    #         }
    #     except Exception as e:
    #         logger.error(f"Error getting controller ID for mission {mission_id} and area {area_id}: {e}")
    #         raise Exception(f"Failed to get controller ID: {e}")

    def get_list_area_by_mission_api(self, mission_id: str) -> Dict[str, Any]:
        """
        Get a list of areas by mission ID.

        Args:
            mission_id (str): The ID of the mission.

        Returns:
            List[Dict[str, Any]]: A list of areas with their names and IDs.
        """
        try: 
            payload = get_list_area_by_mission_api(mission_id=mission_id)
            response = requests.post(
                self.url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            response_data = response.json()
            
            if "data" in response_data and "areas" in response_data["data"]:
                resp = []
                for i in response_data["data"]["areas"]:
                    area_info = {
                        "mission_id": mission_id,
                        "area_name": i["name"],
                        "area_id": i["id"]
                    }
                    resp.append(area_info)
                return resp
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {e}")
        except (KeyError, ValueError) as e:
            raise Exception(f"Failed to parse response: {e}")
        
    def create_program(
            self,
            controller_id: str,
        ) -> Dict[str, Any]:
        """
        Create a new irrigation program.
        
        Args:
            controller_id (str): The ID of the controller to create the program for.

        Returns:
            Dict[str, Any]: The response from the API.
        """
        try:
           
            # controller_info = APIHandler().get_controller_id_by_mission_and_area_id(mission_id=mission_id, area_id=area_id)
            # controller_id = controller_info.get("controller_id")
            logger.info(f"Controller ID: {controller_id}")
            
            
            # Prepare the payload for creating the program
            payload = get_payload_of_create_program_api(controller_id=controller_id)
            logger.info(f"Payload for creating program: {json.dumps(payload, indent=2)}")
            # Make the API request to create the program
            response = requests.post(
                self.url,
                headers=self.headers,
                json=payload
            )
            
            response.raise_for_status()  # Raise an exception for bad status codes
            logger.info(f"Status code: {response.status_code}")
            
            response_data = response.json()
            logger.info(f"Response data: {json.dumps(response_data, indent=2)}")
            
            if "data" in response_data and "create_irrigation_program" in response_data["data"]:
                program_id = response_data["data"]["create_irrigation_program"]
                logger.info(f"Program created successfully with ID: {program_id}")
                return {
                    "program_id": program_id,
                    "controller_id": controller_id,
                }
            else:
                raise ValueError("Invalid response format or program creation failed")
            
        except ValueError as e:
            logger.error(f"Error creating program: {e}")
            raise Exception(f"Failed to create program: {e}")
           
    def list_programs_irrigation_events(
        self,
        program_id: str
    ) -> List[Dict[str, Any]]:
        """
        List all irrigation events for a given program ID.
        
        Args:
            program_id (str): The ID of the irrigation program.
        
        Returns:
            List[Dict[str, Any]]: A list of irrigation events.
        """
        try:
            
            payload = get_payload_of_list_programs_irrigation_envents_api(program_id=program_id)
            logger.info(f"Payload for listing irrigation events: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                self.url,
                headers=self.headers,
                json=payload
            )
            
            response.raise_for_status()  # Raise an exception for bad status codes
            logger.info(f"Status code: {response.status_code}")
            
            response_data = response.json()
            logger.info(f"Response data: {json.dumps(response_data, indent=2)}")
            
            if "data" in response_data and "irrigation_events" in response_data["data"]:
                irrigation_events = response_data["data"]["irrigation_events"]
                logger.info(f"Found {len(irrigation_events)} irrigation events for program {program_id}")
                return irrigation_events   
            else:
                raise ValueError("Invalid response format or no irrigation events found")
            
        except Exception as e:
            logger.error(f"Error listing irrigation events for program {program_id}: {e}")
            raise Exception(f"Failed to list irrigation events: {e}")   
    
    def create_irrigation_events(
        self,
        program_id: str,
        area_id: str,
        dtstart: str,
        quantity: List[int],
        ph_setpoint: float,
        ec_setpoint: float,
        number_of_events: int = 1,
        irrigation_interval: int = 60
    ) -> List[Dict[str, Any]]:
        """
        Create a new irrigation event for a given program ID.
        
        Args:
            program_id (str): The ID of the irrigation program.
            area_id (str): The ID of the irrigation area.
            dtstart (str): The start datetime in timestamp format "%Y-%m-%d %H-%M-%S".
            quantity (List[int]): The quantity values for irrigation.
            ph_setpoint (float): The pH setpoint value.
            ec_setpoint (float): The EC setpoint value.
            number_of_events (int): Number of events to create. Default is 1.
            irrigation_interval (int): Interval between irrigation events in minutes. Default is 60 minutes.
        
        Returns:
            Dict[str, Any]: The response from the API.
        """

        try:
            print(f"Type of dtstart: {type(dtstart)}")
            if isinstance(dtstart, str):
                print(f"dtstart is a string: {dtstart}")
                dtstart = datetime.datetime.strptime(dtstart, "%Y-%m-%d %H:%M:%S")
                dtstart = int(dtstart.timestamp())  * 1000 # Convert to Viet name Unix timestamp
                print(f"Converted dtstart to Unix timestamp: {dtstart}")
            else:
                raise ValueError("dtstart must be a string in the format '%Y-%m-%d %H:%M:%S'")

            responses = []
            for i in range(number_of_events):                
                    payload = get_payload_for_create_irrigation_event_api(
                        program_id=program_id,
                        area_id=area_id,
                        dtstart=dtstart + i * irrigation_interval * 60,
                        quantity=quantity,
                        ph_setpoint=ph_setpoint,
                        ec_setpoint=ec_setpoint
                    )
                    logger.info(f"Payload for creating irrigation event: {json.dumps(payload, indent=2)}")
                    
                    response = requests.post(
                        self.url,
                        headers=self.headers,
                        json=payload
                    )
                    
                    response.raise_for_status()  # Raise an exception for bad status codes
                    logger.info(f"Status code: {response.status_code}")
                    
                    response_data = response.json()
                    logger.info(f"Response data: {json.dumps(response_data, indent=2)}")
                    
                    if "data" in response_data and "create_irrigation_event" in response_data["data"]:
                        event_id = response_data["data"]["create_irrigation_event"]
                        logger.info(f"Irrigation event created successfully with ID: {event_id}")
                        responses.append({
                            "program_id": program_id,
                            "dtstart": dtstart + i * irrigation_interval * 60,  # Increment start time for each event
                            "quantity": quantity,
                            "ph_setpoint": ph_setpoint,
                            "ec_setpoint": ec_setpoint
                        })
                    
            return responses
                
        except Exception as e:
            logger.error(f"Error creating irrigation event {i+1} for program {program_id}: {e}")
            raise Exception(f"Failed to create irrigation event: {e}")

    def get_controllers_by_mission_id(self, mission_id: str) -> List[Dict[str, Any]]:
        """
        Get a list of controllers by mission ID.

        Args:
            mission_id (str): The ID of the mission.

        Returns:
            List[Dict[str, Any]]: A list of controllers with their detailed information.
        """
        try:
            payload = get_payload_for_controllers_api(mission_id=mission_id)
            logger.info(f"Payload for getting controllers: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                self.url,
                headers=self.headers,
                json=payload
            )
            
            response.raise_for_status()  # Raise an exception for bad status codes
            logger.info(f"Status code: {response.status_code}")
            
            response_data = response.json()
            # logger.info(f"Response data: {json.dumps(response_data, indent=2)}")
            
            if "data" in response_data and "controllers" in response_data["data"]:
                results = []
                controllers = response_data["data"]["controllers"]
                for controller in controllers:
                    controller_id = controller.get("id")
                    temp_data = {
                        "controller_id": controller_id,
                        "nodes": []
                    }
                    if controller_id:
                        for node in controller.get("nodes", []):
                            area_id = node.get("area_id")
                            area_name = node.get("area_name")
                            temp = {"area_id": area_id, "area_name": area_name}
                            temp_data["nodes"].append(temp)
                    results.append(temp_data)
                logger.info(f"Found {len(controllers)} controllers for mission {mission_id}")
                return results
            else:
                raise ValueError("Invalid response format or no controllers found")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise Exception(f"Request failed: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse response: {e}")
            raise Exception(f"Failed to parse response: {e}")

    def get_weather_forecast(self) -> Dict[str, Any]:
        """
        Get the weather forecast.
            
        Returns:
            dict: weather data
        """
        try:
            latitude=11.74
            longitude=108.37
            # Setup the Open-Meteo API client with cache and retry on error
            cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
            retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
            openmeteo = openmeteo_requests.Client(session=retry_session)

            # Make sure all required weather variables are listed here
            url = "https://api.open-meteo.com/v1/forecast"
            start_date = datetime.now().strftime('%Y-%m-%d')
            end_date = (datetime.now() + pd.DateOffset(days=1)).strftime('%Y-%m-%d')
            
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "hourly": ["temperature_2m", "relative_humidity_2m", "precipitation_probability", 
                        "apparent_temperature", "et0_fao_evapotranspiration", "rain", "visibility"],
                "models": "best_match",
                "timezone": "Asia/Bangkok",
                "start_date": start_date,
                "end_date": end_date
            }
            responses = openmeteo.weather_api(url, params=params)

            # Process first location
            response = responses[0]
            
            # Process hourly data
            hourly = response.Hourly()
            hourly_temperature_2m = hourly.Variables(0).ValuesAsNumpy()
            hourly_relative_humidity_2m = hourly.Variables(1).ValuesAsNumpy()
            hourly_precipitation_probability = hourly.Variables(2).ValuesAsNumpy()
            hourly_apparent_temperature = hourly.Variables(3).ValuesAsNumpy()
            hourly_et0_fao_evapotranspiration = hourly.Variables(4).ValuesAsNumpy()
            hourly_rain = hourly.Variables(5).ValuesAsNumpy()
            hourly_visibility = hourly.Variables(6).ValuesAsNumpy()

            # Create date range
            date_range = pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            )

            # Build response data
            weather_data = {
                "location": {
                    "latitude": float(response.Latitude()),
                    "longitude": float(response.Longitude()),
                    "elevation": float(response.Elevation()),
                    "timezone": str(response.Timezone())
                },
                "forecast": []
            }

            # Convert numpy arrays to lists and combine with dates
            for i, date in enumerate(date_range):
                if i < len(hourly_temperature_2m):
                    def safe_float_convert(value):
                        """Safely convert numpy value to float or return None"""
                        try:
                            if pd.isna(value) or value is None:
                                return None
                            return float(value)
                        except (ValueError, TypeError):
                            return None
                    
                    weather_data["forecast"].append({
                        "datetime": date.isoformat(),
                        "temperature_2m": safe_float_convert(hourly_temperature_2m[i]),
                        "relative_humidity_2m": safe_float_convert(hourly_relative_humidity_2m[i]),
                        "precipitation_probability": safe_float_convert(hourly_precipitation_probability[i]),
                        "apparent_temperature": safe_float_convert(hourly_apparent_temperature[i]),
                        "et0_fao_evapotranspiration": safe_float_convert(hourly_et0_fao_evapotranspiration[i]),
                        "rain": safe_float_convert(hourly_rain[i]),
                        "visibility": safe_float_convert(hourly_visibility[i])
                    })

            return weather_data

        except Exception as e:
            return {"error": str(e), "status": "failed"}


import cv2
import numpy as np
import requests
import json_numpy
import threading
import time
import queue
import sys
from typing import Dict, Any, Optional

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
except Exception:
    plt = None

# Patch json to handle numpy arrays
json_numpy.patch()

class DroneController:
    def __init__(self, connection_string: str):
        """Establish a MAVLink session and prime controller state.

        Args:
            connection_string: MAVLink endpoint in pymavlink format, for example
                ``udp:127.0.0.1:14550`` or ``udpin:0.0.0.0:14555``.
        """
        self.master = None
        self.connected = False
        self.last_telemetry = None
        self.connect(connection_string)

    def _send_velocity_command(self, vx: float, vy: float, vz: float, yaw_rate: float = 0.0) -> None:
        """Send a velocity setpoint in the local NED frame.

        Args:
            vx: Forward velocity in metres per second (positive north).
            vy: Rightward velocity in metres per second (positive east).
            vz: Downward velocity in metres per second (positive down).
            yaw_rate: Body yaw rate in radians per second.
        """
        if not self.connected:
            return

        # In the LOCAL_NED frame, positive X is north, positive Y is east, positive Z is down.
        self.master.mav.set_position_target_local_ned_send(
            0,
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000011111000111,
            0,
            0,
            0,
            vx,
            vy,
            vz,
            0,
            0,
            0,
            0,
            yaw_rate,
        )

    def _execute_velocity_motion(
        self,
        *,
        vx: float = 0.0,
        vy: float = 0.0,
        yaw_rate: float = 0.0,
        duration: float = 1.0,
        poll_interval: float = 0.1,
    ) -> bool:
        """Fire velocity commands for ``duration`` seconds, then stop."""
        global drone_armed, drone_ready
        
        if not self.connected:
            print("❌ Drone not connected")
            return False

        # Check if drone is armed and in OFFBOARD mode
        if not drone_armed or not drone_ready:
            print("⚠️  Drone not armed/ready. Attempting to arm and enter OFFBOARD mode...")
            if not self.arm_and_offboard():
                print("❌ Failed to arm and enter OFFBOARD mode")
                return False
            print("✅ Drone armed and in OFFBOARD mode")

        duration = max(0.0, float(duration))
        poll_interval = max(0.02, float(poll_interval))

        end_time = time.time() + duration
        try:
            while time.time() < end_time:
                self._send_velocity_command(vx, vy, 0.0, yaw_rate)
                time.sleep(poll_interval)
        finally:
            self._send_velocity_command(0.0, 0.0, 0.0, 0.0)

        return True

    def move_forward(self, distance: float = 2.0, speed: float = 1.0) -> bool:
        """Translate forward by commanding positive X velocity."""
        if speed <= 0:
            raise ValueError("speed must be positive")

        # Forward luôn là vận tốc dương (positive X)
        direction = 1.0 if distance >= 0 else -1.0
        duration = abs(distance) / speed if speed > 0 else 0.0
        return self._execute_velocity_motion(vx=speed * direction, duration=duration)

    def move_backward(self, distance: float = 2.0, speed: float = 1.0) -> bool:
        """Translate backward by commanding negative X velocity."""
        if speed <= 0:
            raise ValueError("speed must be positive")

        # Backward luôn là vận tốc âm (negative X)
        direction = -1.0 if distance >= 0 else 1.0
        duration = abs(distance) / speed if speed > 0 else 0.0
        return self._execute_velocity_motion(vx=speed * direction, duration=duration)

    def move_right(self, distance: float = 2.0, speed: float = 1.0) -> bool:
        """Translate right (positive east) using Y velocity."""
        if speed <= 0:
            raise ValueError("speed must be positive")

        # Right luôn là vận tốc dương (positive Y/East)
        direction = 1.0 if distance >= 0 else -1.0
        duration = abs(distance) / speed if speed > 0 else 0.0
        return self._execute_velocity_motion(vy=speed * direction, duration=duration)

    def move_left(self, distance: float = 2.0, speed: float = 1.0) -> bool:
        """Translate left (negative east) using Y velocity."""
        if speed <= 0:
            raise ValueError("speed must be positive")

        # Left luôn là vận tốc âm (negative Y/East)
        direction = -1.0 if distance >= 0 else 1.0
        duration = abs(distance) / speed if speed > 0 else 0.0
        return self._execute_velocity_motion(vy=speed * direction, duration=duration)

    def turn_around(self, angle_deg: float = 180.0, yaw_rate_deg: float = 60.0) -> bool:
        """Rotate the vehicle about its yaw axis."""
        if yaw_rate_deg <= 0:
            raise ValueError("yaw_rate_deg must be positive")

        angle_sign = 1.0 if angle_deg >= 0 else -1.0
        yaw_rate_rad = math.radians(yaw_rate_deg) * angle_sign
        duration = abs(angle_deg) / yaw_rate_deg if yaw_rate_deg > 0 else 0.0
        return self._execute_velocity_motion(yaw_rate=yaw_rate_rad, duration=duration)

    @staticmethod
    def _meters_to_latlon(lat: float, lon: float, north_m: float, east_m: float) -> Dict[str, float]:
        """Convert local offsets in metres to geodetic coordinates.

        Args:
            lat: Reference latitude in decimal degrees.
            lon: Reference longitude in decimal degrees.
            north_m: Offset north in metres relative to the reference point.
            east_m: Offset east in metres relative to the reference point.

        Returns:
            Dictionary with ``lat`` and ``lon`` keys describing the new coordinate.
        """
        lat_offset = north_m / METERS_PER_DEGREE_LAT
        lon_denom = METERS_PER_DEGREE_LAT * math.cos(math.radians(lat))
        lon_offset = 0.0 if abs(lon_denom) < 1e-9 else east_m / lon_denom
        return {"lat": lat + lat_offset, "lon": lon + lon_offset}

    @staticmethod
    def _latlon_to_offsets(lat: float, lon: float, origin_lat: float, origin_lon: float) -> Dict[str, float]:
        """Convert geodetic coordinates to local planar offsets.

        Args:
            lat: Latitude of the target location in decimal degrees.
            lon: Longitude of the target location in decimal degrees.
            origin_lat: Latitude of the origin in decimal degrees.
            origin_lon: Longitude of the origin in decimal degrees.

        Returns:
            Dictionary with ``north`` and ``east`` offsets in metres.
        """
        north = (lat - origin_lat) * METERS_PER_DEGREE_LAT
        lon_scale = METERS_PER_DEGREE_LAT * math.cos(math.radians(origin_lat))
        east = 0.0 if abs(lon_scale) < 1e-9 else (lon - origin_lon) * lon_scale
        return {"north": north, "east": east}

    @staticmethod
    def _compute_total_distance(waypoints: List[Dict[str, float]]) -> float:
        """Sum segment distances (horizontal + vertical) for the waypoint list.

        Args:
            waypoints: Sequence of waypoint dictionaries containing ``north_offset_m``,
                ``east_offset_m``, and ``alt`` values.

        Returns:
            Total travel distance in metres when visiting waypoints in order.
        """
        total = 0.0
        for current, nxt in zip(waypoints, waypoints[1:]):
            horiz = math.hypot(
                nxt["north_offset_m"] - current["north_offset_m"],
                nxt["east_offset_m"] - current["east_offset_m"]
            )
            vert = abs(nxt["alt"] - current["alt"])
            total += math.hypot(horiz, vert)
        return total

    @staticmethod
    def _latlon_to_tile(lat: float, lon: float, zoom: int) -> Dict[str, float]:
        """Convert geographic coordinates to fractional XYZ map tile indices."""
        return webmercator_latlon_to_tile(lat, lon, zoom)

    @staticmethod
    def _tile_to_latlon(tile_x: float, tile_y: float, zoom: int) -> Dict[str, float]:
        """Convert tile indices back to latitude and longitude."""
        return webmercator_tile_to_latlon(tile_x, tile_y, zoom)

    def _fetch_map_background(
        self,
        waypoints: List[Dict[str, float]],
        base_zoom: int = 19,
        max_tiles: int = 6
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a stitched Google tile image covering the waypoint bounds.

        Args:
            waypoints: Waypoint dictionaries containing ``lat``/``lon`` entries.
            base_zoom: Initial tile zoom level to attempt.
            max_tiles: Maximum number of tiles permitted in each axis.

        Returns:
            Dict with ``image`` (PIL.Image) and ``extent`` (lon/lat bounds) or ``None``
            if tiles cannot be fetched.
        """
        if Image is None or not waypoints:
            return None

        lats = [wp["lat"] for wp in waypoints]
        lons = [wp["lon"] for wp in waypoints]

        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        lat_margin = max((max_lat - min_lat) * 0.2, 0.0005)
        lon_margin = max((max_lon - min_lon) * 0.2, 0.0005)

        min_lat -= lat_margin
        max_lat += lat_margin
        min_lon -= lon_margin
        max_lon += lon_margin

        zoom = base_zoom

        for _ in range(6):
            min_tile = self._latlon_to_tile(min_lat, min_lon, zoom)
            max_tile = self._latlon_to_tile(max_lat, max_lon, zoom)

            min_tile_x = int(math.floor(min(min_tile["x"], max_tile["x"])))
            max_tile_x = int(math.floor(max(min_tile["x"], max_tile["x"])))
            min_tile_y = int(math.floor(min(min_tile["y"], max_tile["y"])))
            max_tile_y = int(math.floor(max(min_tile["y"], max_tile["y"])))

            span_x = max_tile_x - min_tile_x + 1
            span_y = max_tile_y - min_tile_y + 1

            if span_x <= max_tiles and span_y <= max_tiles:
                break

            if zoom <= 12:
                return None
            zoom -= 1
        else:
            return None

        tile_size = DEFAULT_TILE_SIZE
        width = (max_tile_x - min_tile_x + 1) * tile_size
        height = (max_tile_y - min_tile_y + 1) * tile_size
        map_img = Image.new("RGB", (width, height))

        any_tile = False
        session = requests.Session()
        try:
            for tile_x in range(min_tile_x, max_tile_x + 1):
                for tile_y in range(min_tile_y, max_tile_y + 1):
                    try:
                        tile_img = fetch_google_map_tile(
                            tile_x,
                            tile_y,
                            zoom,
                            layer=MAP_TILE_LAYER,
                            session=session,
                            timeout=5.0,
                        )
                    except Exception as exc:
                        logger.debug(
                            "Skipped tile (%s,%s) at zoom %s while building background: %s",
                            tile_x,
                            tile_y,
                            zoom,
                            exc,
                        )
                        continue

                    offset_x = (tile_x - min_tile_x) * tile_size
                    offset_y = (tile_y - min_tile_y) * tile_size
                    map_img.paste(tile_img, (offset_x, offset_y))
                    any_tile = True
        finally:
            session.close()

        if not any_tile:
            return None

        top_left = self._tile_to_latlon(min_tile_x, min_tile_y, zoom)
        bottom_right = self._tile_to_latlon(max_tile_x + 1, max_tile_y + 1, zoom)

        extent = [
            top_left["lon"],
            bottom_right["lon"],
            bottom_right["lat"],
            top_left["lat"],
        ]

        return {
            "image": map_img,
            "extent": extent,
        }

    def _get_global_position(self, timeout: float = 2.0) -> Optional[Dict[str, float]]:
        """Fetch the latest GLOBAL_POSITION_INT data if available.

        Args:
            timeout: Maximum seconds to spend polling MAVLink for the message.

        Returns:
            Dictionary with ``lat``, ``lon``, ``alt_m`` and ``relative_alt_m`` or ``None``
            if no data arrives before the timeout.
        """
        if not self.connected:
            return None

        deadline = time.time() + timeout
        while time.time() < deadline:
            while self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=False):
                pass  # flush all old messages
            msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=2)
            # msg = self.master.recv_match(type='GLOBAL_POSITION_INT', blocking=True, timeout=2)
            print("Your msg is: ",  msg)
            if msg:
                try:
                    return {
                        "lat": float(msg.lat) / 1e7,
                        "lon": float(msg.lon) / 1e7,
                        "alt_m": float(msg.alt) / 1000.0,
                        "relative_alt_m": float(msg.relative_alt) / 1000.0,
                    }
                except AttributeError:
                    break
            time.sleep(0.05)
        if msg is None:
            print("⚠️ No new GLOBAL_POSITION_INT message in buffer")
        return None

    def _generate_shape_offsets(self, shape: str, radius: float, spacing: float) -> List[Dict[str, float]]:
        """Build planar N/E offsets for the requested geometric pattern.

        Args:
            shape: Shape identifier such as ``circle`` or ``triangle``.
            radius: Nominal radius or half-span in metres for the pattern.
            spacing: Desired spacing in metres between sequential samples.

        Returns:
            Ordered list of dictionaries with ``north`` and ``east`` offsets in metres.
        """
        shape_key = shape.lower().strip()
        if radius <= 0:
            raise ValueError("radius must be positive")

        if shape_key in {"circle", "circular"}:
            circumference = 2 * math.pi * radius
            step = max(spacing, 1.0)
            point_count = max(6, int(circumference / step))
            offsets = []
            for i in range(point_count):
                angle = 2 * math.pi * i / point_count
                offsets.append({
                    "north": radius * math.cos(angle),
                    "east": radius * math.sin(angle)
                })
            offsets.append(offsets[0])
            return offsets

        if shape_key in {"square", "box"}:
            half = radius
            offsets = [
                {"north": half, "east": -half},
                {"north": half, "east": half},
                {"north": -half, "east": half},
                {"north": -half, "east": -half},
                {"north": half, "east": -half}
            ]
            return offsets

        if shape_key in {"triangle", "triangular"}:
            offsets = []
            for angle_deg in (90, 210, 330):
                angle = math.radians(angle_deg)
                offsets.append({
                    "north": radius * math.cos(angle),
                    "east": radius * math.sin(angle)
                })
            offsets.append(offsets[0])
            return offsets

        if shape_key in {"line", "straight"}:
            return [
                {"north": -radius, "east": 0.0},
                {"north": 0.0, "east": 0.0},
                {"north": radius, "east": 0.0}
            ]

        if shape_key in {"figure8", "figure-8", "lemniscate"}:
            step = max(spacing, 1.0)
            point_count = max(12, int((2 * math.pi * radius) / step))
            offsets = []
            for i in range(point_count):
                t = 2 * math.pi * i / point_count
                north = radius * math.sin(t)
                east = radius * math.sin(t) * math.cos(t)
                offsets.append({"north": north, "east": east})
            offsets.append(offsets[0])
            return offsets

        raise ValueError(f"Unsupported shape '{shape}'. Supported shapes: circle, square, triangle, line, figure8")

    def _save_waypoint_plot(self, waypoints: List[Dict[str, float]], metadata: Dict[str, Any], output_path: Path) -> Optional[Path]:
        """Render waypoints over an optional map background and persist the image.

        Args:
            waypoints: Waypoint entries containing ``lat``/``lon``.
            metadata: Mission metadata used for titles and annotations.
            output_path: Path where the PNG should be written.

        Returns:
            ``Path`` to the saved preview image, or ``None`` if rendering fails.
        """
        if plt is None:
            print("⚠️ Matplotlib not available - skipping map rendering")
            return None

        try:
            lats = [wp["lat"] for wp in waypoints]
            lons = [wp["lon"] for wp in waypoints]

            fig, ax = plt.subplots(figsize=(8, 6))
            map_background = self._fetch_map_background(waypoints)
            if map_background:
                map_array = np.array(map_background["image"])
                extent = map_background["extent"]
                ax.imshow(map_array, extent=extent, origin='upper')
                ax.set_xlim(extent[0], extent[1])
                ax.set_ylim(extent[2], extent[3])

            ax.plot(lons, lats, marker='o', color="#87E98C", linewidth=2, markersize=6)
            ax.scatter(lons[0], lats[0], color='#1565C0', s=100, zorder=5, label='Start')
            ax.scatter(lons[-1], lats[-1], color="#ED8181", s=100, zorder=5, label='End')

            for idx, (lon, lat) in enumerate(zip(lons, lats), start=1):
                ax.annotate(
                    str(idx),
                    (lon, lat),
                    textcoords='offset points',
                    xytext=(4, 4),
                    fontsize=8,
                    color="white",               # ✅ WHITE TEXT
                    fontweight="bold",
                    bbox=dict(
                        boxstyle="round,pad=0.15",
                        fc="black",              # optional background for visibility
                        ec="none",
                        alpha=0.6,
                    )
                )


            # ax.set_title(f"Flight Path: {metadata.get('shape', 'unknown').title()} ({len(waypoints)} pts)")
            ax.legend()
            ax.grid(alpha=0.3)

            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)  # Hide axis frame for cleaner export

            fig.tight_layout()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(output_path, dpi=200, bbox_inches='tight', pad_inches=0)
            plt.close(fig)
            return output_path
        except Exception as exc:
            plt.close()
            print(f"⚠️ Failed to generate waypoint plot: {exc}")
            return None

    def create_flight_path(
        self,
        shape: str,
        center_lat: float,
        center_lon: float,
        altitude: float,
        radius: float = 20.0,
        waypoint_spacing: float = 5.0,
        hold_seconds: float = 2.0,
        output_dir: Optional[str] = None,
        metadata_overrides: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a geometric flight path and persist JSON + preview image.

        Args:
            shape: Pattern to generate (circle, square, triangle, line, figure8).
            center_lat: Latitude of the mission centre point.
            center_lon: Longitude of the mission centre point.
            altitude: Altitude in metres referenced to the home frame.
            radius: Radius or half side-length in metres for the pattern.
            waypoint_spacing: Target spacing in metres between generated points.
            hold_seconds: Default dwell time at each waypoint in seconds.
            output_dir: Directory where JSON and preview assets are stored.
            metadata_overrides: Optional metadata to merge into the output payload.

        Returns:
            Mission payload containing metadata, waypoints, and file references.
        """
        output_root = Path(output_dir).expanduser() if output_dir else DEFAULT_MISSION_DIR
        output_root.mkdir(parents=True, exist_ok=True)

        offsets = self._generate_shape_offsets(shape, radius, waypoint_spacing)
        waypoints: List[Dict[str, float]] = []
        shape_key = shape.lower().strip()

        for index, offset in enumerate(offsets):
            coord = self._meters_to_latlon(center_lat, center_lon, offset["north"], offset["east"])
            waypoints.append({
                "index": index,
                "lat": round(coord["lat"], 7),
                "lon": round(coord["lon"], 7),
                "alt": float(altitude),
                "north_offset_m": float(offset["north"]),
                "east_offset_m": float(offset["east"]),
                "hold_seconds": float(hold_seconds)
            })

        total_distance = self._compute_total_distance(waypoints)

        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        metadata: Dict[str, Any] = {
            "shape": shape_key,
            "center_lat": float(center_lat),
            "center_lon": float(center_lon),
            "altitude": float(altitude),
            "radius_m": float(radius),
            "waypoint_spacing_m": float(waypoint_spacing),
            "hold_seconds_default": float(hold_seconds),
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "total_waypoints": len(waypoints),
            "total_distance_m": total_distance,
            "position_tolerance_m": 0.8
        }

        if metadata_overrides:
            metadata.update(metadata_overrides)

        base_name = f"{timestamp}_{shape_key}"
        json_path = output_root / f"{base_name}.json"
        mission_payload: Dict[str, Any] = {
            "metadata": metadata,
            "waypoints": waypoints
        }

        with json_path.open("w", encoding="utf-8") as handle:
            json.dump(mission_payload, handle, indent=2)

        image_path = self._save_waypoint_plot(waypoints, metadata, output_root / f"{base_name}.png")

        files_block: Dict[str, Optional[str]] = {"json": str(json_path)}
        if image_path:
            files_block["preview"] = str(image_path)
        mission_payload["files"] = files_block

        print(f"🗺️ Flight path saved: {json_path}")
        if image_path:
            print(f"🖼️ Preview saved: {image_path}")

        return mission_payload

    def execute_flight_path(
        self,
        mission_file: str,
        connection_string: Optional[str] = None,
        takeoff_altitude: Optional[float] = None,
        position_tolerance: float = 0.8,
        timeout_per_waypoint: float = 30.0,
        hold_time_override: Optional[float] = None
    ) -> bool:
        """Load a mission JSON and fly the contained waypoints.

        Args:
            mission_file: Path to the saved mission JSON file.
            connection_string: MAVLink endpoint if a new connection is required.
            takeoff_altitude: Optional override for target altitude in metres.
            position_tolerance: Horizontal tolerance in metres for reaching a waypoint.
            timeout_per_waypoint: Seconds allowed per waypoint before giving up.
            hold_time_override: Optional dwell time override in seconds.

        Returns:
            ``True`` when all waypoints are processed, raising on fatal errors.
        """
        global takeoff_geodetic

        mission_path = Path(mission_file).expanduser()
        if not mission_path.exists():
            raise FileNotFoundError(f"Mission file not found: {mission_path}")

        with mission_path.open("r", encoding="utf-8") as handle:
            mission_data = json.load(handle)

        waypoints = mission_data.get("waypoints")
        metadata = mission_data.get("metadata", {})

        if not waypoints:
            raise ValueError("Mission file does not contain any waypoints")

        if not self.connected:
            if not connection_string:
                raise RuntimeError("Drone not connected and no connection string provided")
            if not self.connect(connection_string):
                raise RuntimeError("Failed to connect to drone")

        if not drone_armed:
            if not self.arm_and_offboard():
                raise RuntimeError("Failed to arm drone")

        altitude_target = takeoff_altitude or metadata.get("altitude")
        if altitude_target is None:
            altitude_target = waypoints[0].get("alt", 10.0)
        altitude_target = float(altitude_target)

        if not drone_ready:
            if not self.takeoff_to_altitude(altitude_target):
                raise RuntimeError("Failed to reach target altitude")

        if takeoff_position is None:
            raise RuntimeError("Takeoff position is not set; ensure arm_and_offboard completed successfully")

        if takeoff_geodetic is None:
            geo = self._get_global_position()
            if geo:
                takeoff_geodetic = geo
                print(f"🌐 Using current geodetic reference: lat={geo['lat']:.7f}, lon={geo['lon']:.7f}")
            else:
                print("⚠️ Global position unavailable; executing mission relative to local origin")

        if takeoff_geodetic:
            reference_lat = takeoff_geodetic["lat"]
            reference_lon = takeoff_geodetic["lon"]
        else:
            reference_lat = metadata.get("center_lat", waypoints[0]["lat"])
            reference_lon = metadata.get("center_lon", waypoints[0]["lon"])

        print(f"🚀 Executing mission '{mission_path.name}' with {len(waypoints)} waypoints")

        for waypoint in waypoints:
            hold_seconds = hold_time_override if hold_time_override is not None else float(
                waypoint.get("hold_seconds", metadata.get("hold_seconds_default", 2.0))
            )
            alt = float(waypoint.get("alt", altitude_target))

            if takeoff_geodetic:
                offsets = self._latlon_to_offsets(
                    waypoint["lat"],
                    waypoint["lon"],
                    reference_lat,
                    reference_lon,
                )
                north = offsets["north"]
                east = offsets["east"]
            else:
                north = waypoint.get("north_offset_m")
                east = waypoint.get("east_offset_m")
                if north is None or east is None:
                    offsets = self._latlon_to_offsets(
                        waypoint["lat"],
                        waypoint["lon"],
                        reference_lat,
                        reference_lon,
                    )
                    north = offsets["north"]
                    east = offsets["east"]

            target_x = takeoff_position[0] + north
            target_y = takeoff_position[1] + east
            target_z = -alt

            start_time = time.time()
            reached = False

            while time.time() - start_time < timeout_per_waypoint:
                self.master.mav.set_position_target_local_ned_send(
                    0,
                    self.master.target_system,
                    self.master.target_component,
                    mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                    0b0000111111111000,
                    target_x,
                    target_y,
                    target_z,
                    0, 0, 0,
                    0, 0, 0,
                    0, 0
                )

                telem = self.get_telemetry()
                if telem:
                    pos = telem['position']
                    horizontal_error = math.hypot(pos[0] - target_x, pos[1] - target_y)
                    vertical_error = abs(pos[2] - alt)
                    if horizontal_error <= position_tolerance and vertical_error <= 0.5:
                        reached = True
                        break

                time.sleep(0.1)

            if reached:
                print(f"✅ Waypoint {waypoint.get('index', '?')} reached (hold {hold_seconds:.1f}s)")
            else:
                print(f"⚠️ Waypoint {waypoint.get('index', '?')} not reached within timeout")

            if hold_seconds > 0:
                time.sleep(hold_seconds)

        print("🎉 Mission execution complete")
        return True

    def upload_mission(
        self, 
        mission_file: str, 
        takeoff_altitude: Optional[float] = None,
        speed: Optional[float] = None
    ) -> bool:
        """Upload mission waypoints to PX4 autopilot using MISSION_ITEM_INT protocol.
        
        This is a helper function that reads a mission JSON file and uploads all waypoints
        to the drone's autopilot memory. The mission is uploaded but NOT started automatically.
        
        Args:
            mission_file: Path to the mission JSON file containing waypoints.
            takeoff_altitude: Optional altitude override for all waypoints.
            speed: Optional flight speed in m/s (e.g., 5.0 for 5 m/s). If not provided, uses PX4 default.
            
        Returns:
            True if mission upload succeeds, False otherwise.
            
        Raises:
            FileNotFoundError: If mission file doesn't exist.
            ValueError: If mission file is invalid or contains no waypoints.
            RuntimeError: If upload fails or drone not connected.
        """
        mission_path = Path(mission_file).expanduser()
        if not mission_path.exists():
            raise FileNotFoundError(f"Mission file not found: {mission_path}")

        # Read mission JSON
        with mission_path.open("r", encoding="utf-8") as handle:
            mission_data = json.load(handle)

        waypoints = mission_data.get("waypoints")
        metadata = mission_data.get("metadata", {})

        if not waypoints:
            raise ValueError("Mission file does not contain any waypoints")

        if not self.connected:
            raise RuntimeError("Drone not connected. Call connect() first.")
        
        # Verify connection with heartbeat check
        print("🔍 Verifying connection...")
        hb = self.master.recv_match(type='HEARTBEAT', blocking=True, timeout=3.0)
        if hb:
            mode = mavutil.mode_string_v10(hb)
            print(f"✅ Heartbeat OK - System: {self.master.target_system}, Mode: {mode}")
        else:
            print("⚠️  No heartbeat received - connection may be unstable")

        print(f"\n📤 UPLOADING MISSION: {mission_path.name}")
        print(f"   Total waypoints: {len(waypoints)}")
        print(f"   Shape: {metadata.get('shape', 'unknown')}")
        print(f"   Distance: {metadata.get('total_distance_m', 0):.1f}m")

        # Step 1: Clear existing mission
        print("🧹 Clearing existing mission...")
        self.master.mav.mission_clear_all_send(
            self.master.target_system,
            self.master.target_component
        )
        
        # Wait for clear ACK
        clear_ack = self.master.recv_match(type='MISSION_ACK', blocking=True, timeout=3.0)
        if clear_ack:
            print("✅ Mission cleared")
        else:
            print("⚠️  No clear ACK (continuing anyway)")
        time.sleep(0.5)
        
        # Flush old messages from queue
        flushed = 0
        while self.master.recv_match(blocking=False):
            flushed += 1
        if flushed > 0:
            print(f"🧹 Flushed {flushed} old messages from queue")

        # Step 2: Send mission count (waypoints + speed command if provided)
        total_items = len(waypoints)
        if speed is not None:
            total_items += 1  # Add 1 for MAV_CMD_DO_CHANGE_SPEED
            print(f"📊 Sending mission count: {len(waypoints)} waypoints + 1 speed command")
        else:
            print(f"📊 Sending mission count: {len(waypoints)} waypoints")
            
        self.master.mav.mission_count_send(
            self.master.target_system,
            self.master.target_component,
            total_items,
            mavutil.mavlink.MAV_MISSION_TYPE_MISSION  # Mission type
        )
        print(f"📤 Sent to system={self.master.target_system}, component={self.master.target_component}")
        
        if speed is not None:
            print(f"⚡ Speed will be set to: {speed} m/s")

        # Step 3: Upload items one by one when PX4 requests them
        uploaded = 0
        item_index = 0
        
        # Upload speed command first if provided
        if speed is not None:
            # Wait for PX4 to request item 0
            print(f"⏳ Waiting for PX4 to request item {item_index} (speed command)...", end=" ")
            start_wait = time.time()
            req = None
            while time.time() - start_wait < 10.0:
                msg = self.master.recv_match(blocking=True, timeout=1.0)
                if msg:
                    msg_type = msg.get_type()
                    if msg_type in ["MISSION_REQUEST_INT", "MISSION_REQUEST"]:
                        req = msg
                        print(f"✅ Got {msg_type}")
                        break

            if not req:
                print(f"\n❌ Timeout waiting for speed command request")
                return False

            # Send MAV_CMD_DO_CHANGE_SPEED
            self.master.mav.mission_item_int_send(
                self.master.target_system,
                self.master.target_component,
                item_index,                                     # seq
                mavutil.mavlink.MAV_FRAME_MISSION,             # frame
                mavutil.mavlink.MAV_CMD_DO_CHANGE_SPEED,       # command
                0,                                              # current
                1,                                              # autocontinue
                1,                                              # param1: speed type (1 = ground speed)
                float(speed),                                   # param2: speed (m/s)
                -1,                                             # param3: throttle (-1 = no change)
                0,                                              # param4: relative (0 = absolute)
                0, 0, 0                                         # x, y, z (unused)
            )
            uploaded += 1
            item_index += 1
            print(f"   ⚡ Uploaded speed command: {speed} m/s")

        # Upload waypoints
        for i, wp in enumerate(waypoints):
            # Wait for PX4 to request this item
            print(f"⏳ Waiting for PX4 to request item {item_index} (waypoint {i+1}/{len(waypoints)})...", end=" ")
            
            # Debug: Check any incoming messages
            start_wait = time.time()
            req = None
            while time.time() - start_wait < 10.0:
                msg = self.master.recv_match(blocking=True, timeout=1.0)
                if msg:
                    msg_type = msg.get_type()
                    if msg_type in ["MISSION_REQUEST_INT", "MISSION_REQUEST"]:
                        req = msg
                        print(f"✅ Got {msg_type}")
                        break
                    else:
                        print(f"[{msg_type}]", end=" ")

            if not req:
                print(f"\n❌ Timeout waiting for item {item_index} request after 10 seconds")
                print("💡 Possible causes:")
                print("   - PX4 not ready to accept mission")
                print("   - SITL/Hardware not running")
                print("   - MAVLink connection dropped")
                return False

            if req.seq != item_index:
                print(f"⚠️  PX4 requested seq {req.seq}, expected {item_index} (continuing)")

            # Determine altitude
            alt = float(wp.get("alt", takeoff_altitude or 10.0))
            if takeoff_altitude is not None:
                alt = float(takeoff_altitude)

            # Send waypoint using MISSION_ITEM_INT (GPS coordinates with int32 precision)
            self.master.mav.mission_item_int_send(
                self.master.target_system,
                self.master.target_component,
                item_index,                                     # seq
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,  # frame
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,          # command
                0,                                              # current (0 = not current)
                1,                                              # autocontinue
                float(wp.get("hold_seconds", 0)),              # param1: hold time
                0,                                              # param2: acceptance radius
                0,                                              # param3: pass radius
                float('nan'),                                   # param4: yaw
                int(wp["lat"] * 1e7),                          # x: latitude * 10^7
                int(wp["lon"] * 1e7),                          # y: longitude * 10^7
                alt                                             # z: altitude
            )
            uploaded += 1
            item_index += 1
            print(f"   ✅ Uploaded waypoint {i+1}/{len(waypoints)}: "
                  f"({wp['lat']:.6f}, {wp['lon']:.6f}) @ {alt:.1f}m")

        # Step 4: Wait for ACK
        try:
            ack = self.master.recv_match(type='MISSION_ACK', blocking=True, timeout=5.0)
            if ack and ack.type == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                if speed is not None:
                    print(f"✅ MISSION UPLOAD COMPLETE! ({len(waypoints)} waypoints + speed {speed} m/s)")
                else:
                    print(f"✅ MISSION UPLOAD COMPLETE! ({len(waypoints)} waypoints)")
                return True
            else:
                ack_type = ack.type if ack else "TIMEOUT"
                print(f"❌ Mission upload failed: ACK type = {ack_type}")
                return False
        except Exception as e:
            print(f"❌ Error waiting for mission ACK: {e}")
            return False

    def execute_flight_path_mission_mode(
        self,
        mission_file: str,
        connection_string: Optional[str] = None,
        takeoff_altitude: Optional[float] = None,
        position_tolerance: float = 0.8,
        timeout_per_waypoint: float = 30.0,
        hold_time_override: Optional[float] = None,
        speed: Optional[float] = None
    ) -> bool:
        """Execute a mission JSON file using PX4 AUTO.MISSION mode (autonomous flight).
        
        This method uploads the mission waypoints to PX4 autopilot and then switches to
        AUTO.MISSION mode for autonomous execution. Unlike the old OFFBOARD approach,
        this does NOT require continuous setpoint streaming.
        
        The drone will:
        1. Upload all waypoints to autopilot memory
        2. Arm if not already armed
        3. Switch to AUTO.MISSION mode
        4. Start autonomous mission execution
        5. Fly through all waypoints independently
        
        Args:
            mission_file: Path to the saved mission JSON file.
            connection_string: MAVLink endpoint if a new connection is required.
            takeoff_altitude: Optional override for target altitude in metres.
            position_tolerance: (Unused - kept for backward compatibility)
            timeout_per_waypoint: (Unused - kept for backward compatibility)
            hold_time_override: (Unused - kept for backward compatibility)
            speed: Optional flight speed in m/s. If provided, sets cruise speed for the mission.

        Returns:
            ``True`` when mission upload and start succeed, raises exception on failure.
            
        Raises:
            FileNotFoundError: Mission file not found.
            ValueError: Invalid mission file.
            RuntimeError: Connection, upload, or mode switch failures.
            
        Example:
            controller = DroneController("udpin:0.0.0.0:14555")
            controller.execute_flight_path("missions/circle.json", takeoff_altitude=15.0)
        """

        print("[Agent] Starting execute_flight_path_mission_mode")
        global takeoff_geodetic, drone_armed

        mission_path = Path(mission_file).expanduser()
        if not mission_path.exists():
            raise FileNotFoundError(f"Mission file not found: {mission_path}")

        # Ensure MAVLink connection
        if not self.connected:
            if not connection_string:
                raise RuntimeError("Drone not connected and no connection string provided")
            if not self.connect(connection_string):
                raise RuntimeError("Failed to connect to drone")

        print("\n" + "="*70)
        print("🚁 MISSION EXECUTION: AUTO.MISSION MODE (AUTONOMOUS FLIGHT)")
        print("="*70)

        # Load mission file to get waypoint count
        with open(mission_path, 'r') as f:
            mission_data = json.load(f)
        waypoints = mission_data.get("waypoints", [])
        total_waypoints = len(waypoints)

        # Upload mission to PX4
        if not self.upload_mission(mission_file, takeoff_altitude, speed):
            raise RuntimeError("Mission upload failed")

        # Get current GPS position for reference
        geo = self._get_global_position(timeout=2.0)
        if geo:
            takeoff_geodetic = geo
            print(f"\n🌍 Current GPS position:")
            print(f"   Lat: {geo['lat']:.7f}")
            print(f"   Lon: {geo['lon']:.7f}")
            print(f"   Alt: {geo.get('relative_alt_m', 0):.1f}m")
        else:
            print("⚠️  Could not read GPS position (continuing anyway)")

        # Arm the drone
        print("\n🔓 Arming drone...")
        for attempt in range(3):
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0,      # confirmation
                1,      # param1: 1 = arm, 0 = disarm
                0, 0, 0, 0, 0, 0
            )
            time.sleep(0.5)
        
        drone_armed = True
        print("✅ Drone armed")

        # Switch to AUTO.MISSION mode
        print("\n🎮 Switching to AUTO.MISSION mode...")
        try:
            self.master.set_mode_px4('AUTO.MISSION', 0, 0)
            time.sleep(1.0)
            print("✅ Mode switched to AUTO.MISSION")
        except Exception as e:
            print(f"⚠️  Mode switch warning: {e}")
            print("   (Continuing - mode may have switched successfully)")

        # Start mission execution
        print("\n🚀 Starting mission execution...")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_MISSION_START,
            0,      # confirmation
            0,      # param1: first mission item (0 = start from beginning)
            0,      # param2: last mission item (0 = all)
            0, 0, 0, 0, 0
        )
        time.sleep(0.5)

        print("\n" + "="*70)
        print("🎯 MISSION STARTED!")
        print("="*70)
        print("🛰️  Drone is now flying AUTONOMOUSLY")
        print("📡 Monitoring mission progress...")
        print("="*70 + "\n")

        # Monitor mission progress
        total_waypoints = len(waypoints)
        current_waypoint = 0
        waypoints_reached = set()  # Track waypoints đã báo để tránh duplicate
        mission_completed = False
        last_update_time = time.time()
        timeout_mission = 600  # 10 phút timeout cho toàn bộ mission
        start_time = time.time()

        print(f"� Total waypoints: {total_waypoints}")
        print("⏳ Waiting for mission to complete...\n")

        # Debug counters
        msg_count = 0
        mission_current_count = 0
        mission_reached_count = 0
        
        while not mission_completed:
            # Kiểm tra timeout tổng
            if time.time() - start_time > timeout_mission:
                print(f"⚠️ Mission timeout after {timeout_mission} seconds")
                break

            # Đọc MAVLink messages với timeout ngắn để responsive
            msg = self.master.recv_match(blocking=True, timeout=0.1)

            if msg:
                msg_count += 1
                msg_type = msg.get_type()

                # MISSION_CURRENT: Waypoint hiện tại đang bay
                if msg_type == 'MISSION_CURRENT':
                    mission_current_count += 1
                    seq = msg.seq
                    if seq != current_waypoint:
                        current_waypoint = seq
                        last_update_time = time.time()
                        print(f"🛫 Flying to waypoint {current_waypoint + 1}/{total_waypoints}")

                # MISSION_ITEM_REACHED: Đã đến waypoint
                elif msg_type == 'MISSION_ITEM_REACHED':
                    mission_reached_count += 1
                    seq = msg.seq
                    # Chỉ print nếu chưa báo waypoint này
                    if seq not in waypoints_reached:
                        waypoints_reached.add(seq)
                        print(f"✅ Reached waypoint {seq + 1}/{total_waypoints}")
                        last_update_time = time.time()  # Reset timer khi có waypoint mới

                # MISSION_RESULT: PX4 báo mission hoàn thành hoặc failed
                elif msg_type == 'MISSION_RESULT':
                    result = msg.result
                    if result == mavutil.mavlink.MAV_MISSION_ACCEPTED:
                        print("\n" + "="*70)
                        print("🎯 MISSION COMPLETED SUCCESSFULLY (PX4 confirmed via MISSION_RESULT)")
                        print("="*70)
                        print(f"📊 Debug stats: {msg_count} messages, {mission_current_count} MISSION_CURRENT, {mission_reached_count} MISSION_ITEM_REACHED")
                        mission_completed = True
                        break
                    else:
                        print(f"\n⚠️ Mission result: {result}")

                # STATUSTEXT: Text messages từ PX4 (có thể chứa "Mission finished")
                elif msg_type == 'STATUSTEXT':
                    text = msg.text.lower()
                    if 'mission' in text and ('finish' in text or 'complete' in text or 'done' in text):
                        print(f"📢 PX4: {msg.text}")
                        print("\n" + "="*70)
                        print("🎯 MISSION COMPLETED (PX4 confirmed via STATUSTEXT)")
                        print("="*70)
                        print(f"📊 Debug stats: {msg_count} messages, {mission_current_count} MISSION_CURRENT, {mission_reached_count} MISSION_ITEM_REACHED")
                        mission_completed = True
                        break

                # Kiểm tra mode - KHÔNG cảnh báo nếu có AUTO flag
                elif msg_type == 'HEARTBEAT':
                    base_mode = msg.base_mode
                    
                    # Check nếu có AUTO flag enabled (bit 7 = 128)
                    if base_mode & mavutil.mavlink.MAV_MODE_FLAG_AUTO_ENABLED:
                        # Vẫn trong AUTO mode - OK, không cảnh báo
                        pass
                    else:
                        # Mode thực sự KHÔNG còn AUTO - có thể bị interrupt
                        mode_name = mavutil.mode_string_v10(msg)
                        # print(f"⚠️ Mode changed to {mode_name} (not AUTO), mission may have been interrupted")

            # Fallback: Nếu đã đến tất cả waypoints và 5 giây không có update mới
            # => Coi như mission hoàn thành (PX4 có thể không gửi MISSION_RESULT trong SITL)
            if len(waypoints_reached) >= total_waypoints:
                time_since_last = time.time() - last_update_time
                if time_since_last > 5:  # 5 giây không có update
                    print("\n" + "="*70)
                    print("🎯 MISSION COMPLETED (all waypoints reached)")
                    print("="*70)
                    print(f"📊 Waypoints reached: {len(waypoints_reached)}/{total_waypoints}")
                    print(f"📊 Debug stats: {msg_count} messages, {mission_current_count} MISSION_CURRENT, {mission_reached_count} MISSION_ITEM_REACHED")
                    mission_completed = True
                    break

            # Kiểm tra nếu không có update quá lâu
            if time.time() - last_update_time > 120:  # 2 phút không có update
                print("⚠️ No mission update for 2 minutes, mission may be stuck")
                break

        print(f"\n✅ Mission execution finished")
        print(f"📊 Waypoints completed: {current_waypoint + 1}/{total_waypoints}\n")

        return True

    def connect(self, connection_string: str) -> bool:
        """Connect to a MAVLink endpoint.

        Args:
            connection_string: pymavlink connection string to open.

        Returns:
            ``True`` if the heartbeat is received, otherwise ``False``.
        """
        try:
            print("🔗 Connecting to drone...")
            self.master = mavutil.mavlink_connection(connection_string)
            print("⏳ Waiting for heartbeat...")
            self.master.wait_heartbeat(timeout=10)
            print(f"✅ Connected to system {self.master.target_system}, component {self.master.target_component}")
            self.connected = True
            return True
        except Exception as e:
            print(f"❌ Failed to connect to drone: {e}")
            self.connected = False
            return False
    
    def get_telemetry(self) -> Optional[Dict[str, Any]]:
        """Get current drone telemetry.

        Returns:
            Dictionary with position, velocity, orientation and timestamp entries if
            data is available, otherwise the last cached snapshot.
        """
        if not self.connected:
            return self.last_telemetry
        
        try:
            pos_msg = self.master.recv_match(type='LOCAL_POSITION_NED', blocking=False)
            if pos_msg:
                att_msg = self.master.recv_match(type='ATTITUDE', blocking=False)
                
                telemetry = {
                    'position': [float(pos_msg.x), float(pos_msg.y), float(-pos_msg.z)],
                    'velocity': [float(pos_msg.vx), float(pos_msg.vy), float(-pos_msg.vz)],
                    'orientation': [0.0, 0.0, 0.0, 1.0],
                    'gimbal': [0.0, 0.0, 0.0],
                    'timestamp': time.time()
                }
                
                if att_msg:
                    roll, pitch, yaw = att_msg.roll, att_msg.pitch, att_msg.yaw
                    cr = np.cos(roll * 0.5)
                    sr = np.sin(roll * 0.5)
                    cp = np.cos(pitch * 0.5)
                    sp = np.sin(pitch * 0.5)
                    cy = np.cos(yaw * 0.5)
                    sy = np.sin(yaw * 0.5)
                    
                    w = cr * cp * cy + sr * sp * sy
                    x = sr * cp * cy - cr * sp * sy
                    y = cr * sp * cy + sr * cp * sy
                    z = cr * cp * sy - sr * sp * cy
                    
                    telemetry['orientation'] = [float(x), float(y), float(z), float(w)]
                
                self.last_telemetry = telemetry
                return telemetry
                
        except Exception as e:
            print(f"❌ Error getting telemetry: {e}")
        
        return self.last_telemetry

    def get_vehicle_status(self) -> Optional[Dict[str, Any]]:
        """Aggregate UAV status for agent state updates.

        Returns:
            Dictionary containing geodetic coordinates, altitude, velocity,
            battery metrics and flight state flags when telemetry is available.
        """
        if not self.connected or self.master is None:
            return None

        status: Dict[str, Any] = {
            "timestamp": time.time(),
            "armed": bool(drone_armed),
            "is_flying": bool(drone_ready),
        }

        telemetry = self.get_telemetry()
        if telemetry:
            position = telemetry.get("position")
            velocity = telemetry.get("velocity")
            orientation = telemetry.get("orientation")

            if position:
                status["local_position_m"] = [float(value) for value in position]
                status["altitude_m"] = float(position[2])

            if velocity:
                status["local_velocity_m_s"] = [float(value) for value in velocity]

            if orientation:
                status["orientation_quat"] = [float(value) for value in orientation]

        try:
            global_msg = self.master.recv_match(type="GLOBAL_POSITION_INT", blocking=False)
        except Exception:
            global_msg = None

        if global_msg:
            try:
                lat = getattr(global_msg, "lat", None)
                lon = getattr(global_msg, "lon", None)
                rel_alt = getattr(global_msg, "relative_alt", None)
                vx = getattr(global_msg, "vx", None)
                vy = getattr(global_msg, "vy", None)
                vz = getattr(global_msg, "vz", None)

                if lat is not None and lon is not None:
                    status["latitude"] = float(lat) / 1e7
                    status["longitude"] = float(lon) / 1e7

                if rel_alt is not None:
                    status["relative_altitude_m"] = float(rel_alt) / 1000.0

                if None not in (vx, vy, vz):
                    vx_m = float(vx) / 100.0
                    vy_m = float(vy) / 100.0
                    vz_m = float(vz) / 100.0
                    status["ground_speed_m_s"] = math.sqrt(vx_m ** 2 + vy_m ** 2 + vz_m ** 2)
            except (TypeError, ValueError):
                pass

        try:
            battery_msg = self.master.recv_match(type="SYS_STATUS", blocking=False)
        except Exception:
            battery_msg = None

        if battery_msg:
            voltage_mv = getattr(battery_msg, "voltage_battery", None)
            current_ma = getattr(battery_msg, "current_battery", None)
            remaining_pct = getattr(battery_msg, "battery_remaining", None)

            battery: Dict[str, Any] = {}

            if voltage_mv is not None and voltage_mv > 0:
                battery["voltage_v"] = float(voltage_mv) / 1000.0
            if current_ma is not None and current_ma > -1:
                battery["current_a"] = float(current_ma) / 100.0
            if remaining_pct is not None and remaining_pct >= 0:
                battery["remaining_percent"] = float(remaining_pct)

            if battery:
                status["battery"] = battery

        if "relative_altitude_m" in status:
            status["is_flying"] = bool(status["relative_altitude_m"] > HOVER_TOLERANCE)
        elif "altitude_m" in status:
            status["is_flying"] = bool(status["altitude_m"] > HOVER_TOLERANCE)

        return status if len(status) > 3 else None

    def get_current_altitude(self, *, use_global_reference: bool = False) -> Optional[float]:
        """Return the vehicle altitude in metres above the home frame."""
        if use_global_reference:
            geo = self._get_global_position(timeout=0.2)
            if geo and geo.get("relative_alt_m") is not None:
                return float(geo["relative_alt_m"])
            return None

        telemetry = self.get_telemetry()
        if telemetry and telemetry.get("position"):
            try:
                return float(telemetry["position"][2])
            except (IndexError, TypeError, ValueError):
                return None
        return None
    
    def arm_and_offboard(self) -> bool:
        """Arm the drone and switch into OFFBOARD control mode.

        Returns:
            ``True`` when arming succeeds and initial setpoints are accepted.
        """
        global drone_armed, takeoff_position, takeoff_geodetic
        
        print("\n🚁 PREPARING FOR FLIGHT")
        
        # Get initial position
        telem = self.get_telemetry()
        if telem:
            takeoff_position = telem['position'].copy()
            print(f"📍 Takeoff position: X={takeoff_position[0]:.2f}, Y={takeoff_position[1]:.2f}, Z={takeoff_position[2]:.2f}")
        else:
            print("❌ Unable to get current position")
            takeoff_position = [0.0, 0.0, 0.0]
            print("⚠️  Using default takeoff position")

        geo = self._get_global_position()
        if geo:
            takeoff_geodetic = geo
            print(f"🌐 Takeoff geodetic: lat={geo['lat']:.7f}, lon={geo['lon']:.7f}, alt={geo['relative_alt_m']:.1f}m")
        else:
            print("⚠️ Unable to read global GPS position; mission will use local offsets")
        
        # Send initial setpoints (reduced count for faster startup)
        print("📡 Sending initial setpoints...")
        for i in range(100):  # Reduced from 200 to 100
            self.master.mav.set_position_target_local_ned_send(
                0, self.master.target_system, self.master.target_component,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                0b0000111111111000,  # Use position only
                takeoff_position[0], takeoff_position[1], -takeoff_position[2],
                0, 0, 0, 0, 0, 0, 0, 0
            )
            time.sleep(0.002)  # Reduced from 0.005 to 0.002
        
        # ARM (reduced retry attempts)
        print("🔓 Arming drone...")
        for i in range(3):  # Reduced from 5 to 3
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0, 1, 0, 0, 0, 0, 0, 0
            )
            time.sleep(0.1)  # Reduced from 0.2 to 0.1
        
        # Switch to OFFBOARD mode (use MAV_CMD_DO_SET_MODE)
        print("🎮 Switching to OFFBOARD mode...")
        # PX4 custom mode for OFFBOARD is 6
        # MAV_MODE_FLAG_CUSTOM_MODE_ENABLED (1) + MAV_MODE_FLAG_SAFETY_ARMED (128) = 129
        for i in range(3):  # Reduced from 5 to 3
            self.master.set_mode_px4('OFFBOARD', 0, 0)
            time.sleep(0.1)  # Reduced from 0.2 to 0.1
        
        drone_armed = True
        print("✅ Drone armed and ready for OFFBOARD mode")
        return True
    
    def takeoff_to_altitude(self, target_altitude: float) -> bool:
        """Climb to the requested altitude using position setpoints.

        Args:
            target_altitude: Desired altitude above home in metres.

        Returns:
            ``True`` when the vehicle stabilises near the requested altitude.
        """
        global drone_ready
        
        print(f"\n🚀 TAKING OFF TO {target_altitude}m")
        
        if not takeoff_position:
            print("❌ No takeoff position available")
            return False
        
        # Fast takeoff with fewer steps
        altitudes = np.linspace(0.5, target_altitude, 4)  # Reduced from 8 to 4 steps
        
        for alt in altitudes:
            target_z = -alt  # NED frame (negative Z is up)
            print(f"⬆️  Climbing to {alt:.1f}m...")
            
            start_time = time.time()
            while time.time() - start_time < 2.0:  # Reduced from 5 to 2 seconds per step
                self.master.mav.set_position_target_local_ned_send(
                    0, self.master.target_system, self.master.target_component,
                    mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                    0b0000111111111000,  # Use position only
                    takeoff_position[0], takeoff_position[1], target_z,
                    0, 0, 0, 0, 0, 0, 0, 0
                )
                time.sleep(0.05)  # Reduced from 0.1 to 0.05 for faster commands
            
            # Check altitude
            telem = self.get_telemetry()
            if telem:
                current_alt = telem['position'][2]
                error = abs(current_alt - alt)
                if error < HOVER_TOLERANCE:
                    print(f"✅ Reached {alt:.1f}m (actual: {current_alt:.2f}m)")
                else:
                    print(f"⚠️  At {current_alt:.2f}m (target: {alt:.1f}m)")
        
        # Final stabilization (reduced time)
        print(f"🎯 Stabilizing at {target_altitude}m...")
        start_time = time.time()
        stable_count = 0
        
        while time.time() - start_time < 5.0:  # Reduced from 10 to 5 seconds max
            self.master.mav.set_position_target_local_ned_send(
                0, self.master.target_system, self.master.target_component,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                0b0000111111111000,
                takeoff_position[0], takeoff_position[1], -target_altitude,
                0, 0, 0, 0, 0, 0, 0, 0
            )
            
            telem = self.get_telemetry()
            if telem:
                current_alt = telem['position'][2]
                if abs(current_alt - target_altitude) < HOVER_TOLERANCE:
                    stable_count += 1
                    if stable_count >= 20:  # Reduced from 30 to 20 (2 seconds stable at 10Hz)
                        break
                else:
                    stable_count = 0
            
            time.sleep(0.1)
        
        drone_ready = True
        print(f"🎉 TAKEOFF COMPLETE - Drone ready at {target_altitude}m")
        
        return True
    
    def navigate_to_waypoints(self) -> bool:
        """Navigate a simple two-leg path using velocity commands.

        Returns:
            ``True`` when both phases complete, ``False`` if prerequisites fail.
        """
        global drone_ready
        
        print(f"\n🗺️  VELOCITY-BASED NAVIGATION")
        
        if not takeoff_position:
            print("❌ No takeoff position available")
            return False
        
        # Phase 1: Move forward 10 meters using velocity
        print(f"📍 Phase 1: Moving forward 10m using velocity control...")
        target_distance = 10.0
        velocity = 2.0  # 2 m/s forward velocity (faster for longer distance)
        move_time = target_distance / velocity  # 5 seconds

        print(f"   Setting forward velocity: {velocity} m/s for {move_time:.1f} seconds")
        start_time = time.time()
        
        while time.time() - start_time < move_time:
            # Send forward velocity command (X-axis positive = forward)
            self.master.mav.set_position_target_local_ned_send(
                0, self.master.target_system, self.master.target_component,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                0b0000011111000111,  # Use velocity only
                0, 0, 0,  # Position (ignored)
                velocity, 0, 0,  # Velocity: forward, right, down
                0, 0, 0,  # Acceleration (ignored)
                0, 0  # Yaw, yaw_rate
            )
            
            # Show progress
            elapsed = time.time() - start_time
            distance_traveled = velocity * elapsed
            remaining = target_distance - distance_traveled
            
            telem = self.get_telemetry()
            if telem:
                current_pos = telem['position']
                actual_distance = current_pos[0] - takeoff_position[0]
                print(f"   Progress: {elapsed:.1f}s, Target: {distance_traveled:.1f}m, Actual: {actual_distance:.1f}m")
            
            time.sleep(0.1)  # 10Hz
        
        # Stop forward movement
        print("   Stopping forward movement...")
        for _ in range(10):  # 1 second of stop commands
            self.master.mav.set_position_target_local_ned_send(
                0, self.master.target_system, self.master.target_component,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                0b0000011111000111,  # Use velocity only
                0, 0, 0,  # Position (ignored)
                0, 0, 0,  # Velocity: stop
                0, 0, 0,  # Acceleration (ignored)
                0, 0  # Yaw, yaw_rate
            )
            time.sleep(0.1)
        
        print("✅ Forward movement complete")
        
        # Phase 2: Move right 1 meter using velocity
        print(f"📍 Phase 2: Moving right 1m using velocity control...")
        target_distance = 2.0
        velocity = 1.0  # 1 m/s right velocity (slower for precision)
        move_time = target_distance / velocity  # 1 seconds

        print(f"   Setting right velocity: {velocity} m/s for {move_time:.1f} seconds")
        start_time = time.time()
        
        while time.time() - start_time < move_time:
            # Send right velocity command (Y-axis positive = right)
            self.master.mav.set_position_target_local_ned_send(
                0, self.master.target_system, self.master.target_component,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                0b0000011111000111,  # Use velocity only
                0, 0, 0,  # Position (ignored)
                0, velocity, 0,  # Velocity: forward, right, down
                0, 0, 0,  # Acceleration (ignored)
                0, 0  # Yaw, yaw_rate
            )
            
            # Show progress
            elapsed = time.time() - start_time
            distance_traveled = velocity * elapsed
            remaining = target_distance - distance_traveled
            
            telem = self.get_telemetry()
            if telem:
                current_pos = telem['position']
                actual_distance = current_pos[1] - takeoff_position[1]
                print(f"   Progress: {elapsed:.1f}s, Target: {distance_traveled:.1f}m, Actual: {actual_distance:.1f}m")
            
            time.sleep(0.1)  # 10Hz
        
        # Stop right movement
        print("   Stopping right movement...")
        for _ in range(10):  # 1 second of stop commands
            self.master.mav.set_position_target_local_ned_send(
                0, self.master.target_system, self.master.target_component,
                mavutil.mavlink.MAV_FRAME_LOCAL_NED,
                0b0000011111000111,  # Use velocity only
                0, 0, 0,  # Position (ignored)
                0, 0, 0,  # Velocity: stop
                0, 0, 0,  # Acceleration (ignored)
                0, 0  # Yaw, yaw_rate
            )
            time.sleep(0.1)
        
        print("✅ Right movement complete")
        
        # Final position check
        telem = self.get_telemetry()
        if telem:
            final_pos = telem['position']
            dx = final_pos[0] - takeoff_position[0]
            dy = final_pos[1] - takeoff_position[1]
            print(f"🎯 Final position relative to takeoff: X={dx:.2f}m, Y={dy:.2f}m")
            print(f"   Target was: X=10.0m, Y=1.0m")
            print(f"   Error: X={abs(dx-10.0):.2f}m, Y={abs(dy-1.0):.2f}m")
        
        print("🎯 Velocity-based navigation complete!")
        print("🤖 AI control will start in 3 seconds...")
        time.sleep(3)
        
        return True
    
    def land_and_disarm(self):
        """Initiate a simple landing sequence and disarm the vehicle."""
        global running, drone_armed, drone_ready, ai_control_active
        
        print("\n🛬 INITIATING LANDING SEQUENCE")
        
        # Stop AI control
        ai_control_active = False
        drone_ready = False
        
        # Stop movement
        self._send_velocity_command(0.0, 0.0, 0.0, 0.0)
        time.sleep(1)
        
        # Land
        print("📉 Landing...")
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_NAV_LAND,
            0, 0, 0, 0, 0, 0, 0, 0
        )
        
        time.sleep(10)  # Wait for landing
        
        # Disarm
        print("🔒 Disarming...")
        for i in range(3):
            self.master.mav.command_long_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                0, 0, 0, 0, 0, 0, 0, 0
            )
            time.sleep(0.2)
        
        drone_armed = False
        print("✅ Landing complete")
