import os
import requests
import logging

def get_weather(location_data):
    """
    OpenWeatherMap API. location_data can be a dict: 
    {"location": "Delhi", "type": "current" or "forecast", "days": 3}
    """
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key: return "Error: Weather API key missing."

    location = location_data.get("location", "")
    req_type = location_data.get("type", "current")
    
    if not location: return "Location not specified for weather."

    try:
        if req_type == "forecast":
            # 5 Day / 3 Hour Forecast API
            url = f"http://api.openweathermap.org/data/2.5/forecast?q={location}&appid={api_key}&units=metric"
            response = requests.get(url).json()
            
            if response.get("cod") != "200": return f"Weather Error: {response.get('message')}"
            
            days_requested = location_data.get("days", 3)
            results = f"🌤️ WEATHER FORECAST FOR {location.upper()} ({days_requested} Days):\n"
            
            # API returns data every 3 hours (8 items per day). We pick 1 per day (mid-day).
            for item in response['list'][::8][:days_requested]:
                date = item['dt_txt'].split(' ')[0]
                temp = item['main']['temp']
                desc = item['weather'][0]['description']
                results += f"- {date}: {temp}°C, {desc}\n"
            return results
            
        else:
            # Current Weather API
            url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={api_key}&units=metric"
            response = requests.get(url).json()
            
            if response.get("cod") != 200: return f"Weather Error: {response.get('message')}"
            
            temp = response['main']['temp']
            desc = response['weather'][0]['description']
            humidity = response['main']['humidity']
            return f"🌡️ CURRENT WEATHER IN {location.upper()}:\nTemperature: {temp}°C\nCondition: {desc}\nHumidity: {humidity}%"
            
    except Exception as e:
        logging.error(f"Weather API Error: {e}")
        return "Failed to fetch weather data."