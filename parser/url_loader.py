import requests
from typing import Union

def load_from_url(url: str) -> str:
    """Load OpenAPI spec from URL with better error handling"""
    try:
        print(f"🌐 Attempting to fetch from: {url}")
        
        # Add timeout and better headers
        headers = {
            'User-Agent': 'OpenAPI-UI-Generator/1.0',
            'Accept': 'application/json, application/yaml, text/yaml, text/plain'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.reason}")
            
        print(f"✅ Successfully fetched {len(response.text)} characters")
        return response.text
        
    except requests.exceptions.ConnectionError as e:
        if "localhost" in url or "127.0.0.1" in url:
            raise Exception(
                f"❌ Cannot connect to local server: {url}\n"
                f"💡 Make sure your local development server is running.\n"
                f"   Common local URLs:\n"
                f"   • http://localhost:3000/swagger.json\n"
                f"   • http://localhost:8080/v3/api-docs\n"
                f"   • http://localhost:5000/swagger.json"
            )
        else:
            raise Exception(f"❌ Connection failed: {url}\n💡 Check your internet connection and URL")
            
    except requests.exceptions.Timeout:
        raise Exception(f"❌ Request timeout: {url}\n💡 Server took too long to respond")
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"❌ Request failed: {str(e)}")
