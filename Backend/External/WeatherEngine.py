# =============================================================
#  Backend/External/WeatherEngine.py - OpenWeatherMap API
#
#  Kya karta:
#    - Current weather for any city (default: Pune)
#    - 5-day forecast
#    - Spoken-friendly summaries
#    - Emoji icons for GUI display
#    - Cache 10 minutes (avoid API spam)
#
#  FREE tier: 1000 calls/day, 60/min
#
#  Usage:
#    from Backend.External.WeatherEngine import weather
#    result = weather.current()         # Pune default
#    result = weather.current("Mumbai")
#    result = weather.forecast("Pune", days=3)
# =============================================================

import time
from datetime import datetime
from typing import Dict, List, Optional

import requests
from dotenv import dotenv_values

from Backend.Utils.Logger import get_logger
from Backend.Utils.InternetCheck import net
from Backend.Core.ErrorHandler import safe_run

log = get_logger("Weather")

env = dotenv_values(".env")
API_KEY = env.get("OpenWeatherAPIKey", "").strip()
DEFAULT_CITY = env.get("UserCity", "Pune")

BASE_URL = "https://api.openweathermap.org/data/2.5"
UNITS = "metric"  # Celsius

# Cache: {city_lower: (data, timestamp)}
_cache: Dict[str, tuple] = {}
CACHE_TTL = 600  # 10 min

# =============================================================
#  Weather icons mapping
# =============================================================
ICONS = {
    "01d": "sunny",         "01n": "clear-night",
    "02d": "partly-cloudy", "02n": "partly-cloudy",
    "03d": "cloudy",        "03n": "cloudy",
    "04d": "overcast",      "04n": "overcast",
    "09d": "drizzle",       "09n": "drizzle",
    "10d": "rain",          "10n": "rain",
    "11d": "thunder",       "11n": "thunder",
    "13d": "snow",          "13n": "snow",
    "50d": "mist",          "50n": "mist",
}

class WeatherEngine:
    """OpenWeatherMap wrapper."""
    
    def _check_setup(self) -> Optional[Dict]:
        """Validate API key + net. Return error dict or None."""
        if not API_KEY or API_KEY == "paste_here":
            return {"ok": False, "message": "Weather API key not set in .env, Sir."}
        if not net.is_online():
            return {"ok": False, "message": "No internet for weather, Sir."}
        return None
    
    # =========================================================
    #  CURRENT WEATHER
    # =========================================================
    def current(self, city: str = None) -> Dict:
        """Current weather for given city."""
        err = self._check_setup()
        if err:
            return err
        
        city = (city or DEFAULT_CITY).strip()
        cache_key = city.lower()
        
        # Cache check
        if cache_key in _cache:
            data, ts = _cache[cache_key]
            if time.time() - ts < CACHE_TTL:
                return data
        
        try:
            response = requests.get(
                f"{BASE_URL}/weather",
                params={"q": city, "appid": API_KEY, "units": UNITS},
                timeout=8,
            )
            
            if response.status_code == 404:
                return {"ok": False, "message": f"City '{city}' not found, Sir."}
            
            if response.status_code != 200:
                return {"ok": False, "message": f"Weather API error: {response.status_code}"}
            
            data = response.json()
            result = self._parse_current(data, city)
            _cache[cache_key] = (result, time.time())
            return result
        
        except requests.Timeout:
            return {"ok": False, "message": "Weather request timed out, Sir."}
        except Exception as e:
            log.error(f"Weather error: {e}")
            return {"ok": False, "message": f"Weather fetch failed: {str(e)[:60]}"}
    
    def _parse_current(self, data: dict, city: str) -> Dict:
        """Parse API response into clean dict."""
        try:
            main = data.get("main", {})
            weather_arr = data.get("weather", [{}])
            w = weather_arr[0] if weather_arr else {}
            wind = data.get("wind", {})
            
            temp = round(main.get("temp", 0))
            feels = round(main.get("feels_like", 0))
            humidity = main.get("humidity", 0)
            desc = w.get("description", "unknown").capitalize()
            icon_code = w.get("icon", "")
            icon = ICONS.get(icon_code, "unknown")
            wind_speed = round(wind.get("speed", 0) * 3.6, 1)  # m/s -> km/h
            
            # Spoken summary
            city_display = data.get("name", city)
            summary = self._build_summary(
                city=city_display, temp=temp, feels=feels,
                desc=desc, humidity=humidity, wind=wind_speed,
            )
            
            return {
                "ok": True,
                "city": city_display,
                "temp_c": temp,
                "feels_like_c": feels,
                "description": desc,
                "humidity": humidity,
                "wind_kmh": wind_speed,
                "icon": icon,
                "icon_code": icon_code,
                "summary": summary,
                "message": summary,
            }
        except Exception as e:
            log.error(f"Parse error: {e}")
            return {"ok": False, "message": "Could not parse weather data, Sir."}
    
    def _build_summary(self, city: str, temp: int, feels: int,
                       desc: str, humidity: int, wind: float) -> str:
        """Human-friendly spoken summary."""
        parts = [f"Currently {temp} degrees in {city}, Sir."]
        
        if abs(feels - temp) >= 3:
            parts.append(f"Feels like {feels}.")
        
        parts.append(f"{desc}.")
        
        if humidity > 75:
            parts.append(f"Quite humid at {humidity}%.")
        
        if wind > 25:
            parts.append(f"Strong wind at {wind} kilometres per hour.")
        
        return " ".join(parts)
    
    # =========================================================
    #  FORECAST
    # =========================================================
    def forecast(self, city: str = None, days: int = 3) -> Dict:
        """Multi-day forecast summary."""
        err = self._check_setup()
        if err:
            return err
        
        city = (city or DEFAULT_CITY).strip()
        days = max(1, min(5, days))
        
        try:
            response = requests.get(
                f"{BASE_URL}/forecast",
                params={"q": city, "appid": API_KEY, "units": UNITS},
                timeout=10,
            )
            
            if response.status_code != 200:
                return {"ok": False, "message": f"Forecast API error: {response.status_code}"}
            
            data = response.json()
            forecasts = self._parse_forecast(data, days)
            summary = self._build_forecast_summary(city, forecasts, days)
            
            return {
                "ok": True,
                "city": city,
                "days": forecasts,
                "summary": summary,
                "message": summary,
            }
        except Exception as e:
            log.error(f"Forecast error: {e}")
            return {"ok": False, "message": f"Forecast failed: {str(e)[:60]}"}
    
    def _parse_forecast(self, data: dict, days: int) -> List[Dict]:
        """Aggregate 3-hourly data into daily summaries."""
        items = data.get("list", [])
        
        daily: Dict[str, Dict] = {}
        for item in items:
            date_str = item.get("dt_txt", "").split(" ")[0]
            if not date_str:
                continue
            
            temps = item.get("main", {})
            weather = (item.get("weather") or [{}])[0]
            
            if date_str not in daily:
                daily[date_str] = {
                    "date": date_str,
                    "temps": [],
                    "descriptions": [],
                    "icons": [],
                }
            
            daily[date_str]["temps"].append(temps.get("temp", 0))
            daily[date_str]["descriptions"].append(weather.get("description", ""))
            daily[date_str]["icons"].append(weather.get("icon", ""))
        
        result = []
        for date_str in sorted(daily.keys())[:days]:
            d = daily[date_str]
            temps = d["temps"]
            result.append({
                "date": date_str,
                "temp_min": round(min(temps)) if temps else 0,
                "temp_max": round(max(temps)) if temps else 0,
                "description": self._dominant(d["descriptions"]),
                "icon": self._dominant(d["icons"]),
            })
        return result
    
    def _dominant(self, lst: List[str]) -> str:
        """Most frequent string in list."""
        if not lst:
            return ""
        from collections import Counter
        return Counter(lst).most_common(1)[0][0]
    
    def _build_forecast_summary(self, city: str, days: List[Dict], n: int) -> str:
        if not days:
            return f"No forecast data for {city}, Sir."
        
        parts = [f"{n}-day forecast for {city}, Sir:"]
        for d in days[:n]:
            try:
                date = datetime.strptime(d["date"], "%Y-%m-%d").strftime("%A")
            except Exception:
                date = d["date"]
            parts.append(
                f"{date}: {d['temp_min']}-{d['temp_max']} degrees, {d['description']}."
            )
        return " ".join(parts)

# Singleton
weather = WeatherEngine()

# =============================================================
#  TEST
# =============================================================
if __name__ == "__main__":
    print("\n--- WeatherEngine Test ---\n")
    
    if not API_KEY or API_KEY == "paste_here":
        print("[WARN] OpenWeatherAPIKey not set. Get it from https://openweathermap.org/api")
    else:
        print(f"Default city: {DEFAULT_CITY}\n")
        
        print("-- Current weather --")
        r = weather.current()
        print(f"  {r['message']}")
        if r["ok"]:
            print(f"  Temp: {r['temp_c']}C, Feels: {r['feels_like_c']}C")
            print(f"  Humidity: {r['humidity']}%, Wind: {r['wind_kmh']} km/h")
            print(f"  Icon: {r['icon']}")
        
        print("\n-- 3-day forecast --")
        r = weather.forecast(days=3)
        print(f"  {r['message']}")
    
    print("\n[OK] WeatherEngine test complete\n")