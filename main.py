import os
import re
import json
from typing import Any, Dict, List, Optional, Union
from openai import AzureOpenAI
from parser.url_loader import load_from_url
from parser.swagger_parser import parse_swagger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")


def create_purified_api_summary(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Create a clean, comprehensive summary of all API endpoints for LLM consumption"""
    api_summary = {
        "info": {
            "title": parsed['info'].get('title', ''),
            "description": parsed['info'].get('description', ''),
            "version": parsed['info'].get('version', '')
        },
        "baseUrl": parsed.get("servers", [{"url": ""}])[0].get("url", ""),
        "endpoints": []
    }
    
    for path, path_data in parsed["paths"].items():
        http_methods = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']
        operations = {k: v for k, v in path_data.items() if k in http_methods}
        
        for method, op in operations.items():
            endpoint = {
                "path": path,
                "method": method.upper(),
                "operationId": op.get("operationId", ""),
                "summary": op.get("summary", ""),
                "description": op.get("description", ""),
                "parameters": [],
                "requestBody": None,
                "responses": {}
            }
            
            # Parameters with full schema expansion
            for param in op.get("parameters", []):
                schema = param.get("schema") or {}
                param_info = {
                    "name": param.get("name"),
                    "in": param.get("in"),
                    "required": param.get("required", False),
                    "type": schema.get("type", "unknown"),
                    "description": param.get("description", "")
                }
                
                # Handle object parameters (like DummyDto)
                if schema.get("type") == "object" and "properties" in schema:
                    param_info["properties"] = {}
                    for prop_name, prop_schema in schema["properties"].items():
                        param_info["properties"][prop_name] = {
                            "type": prop_schema.get("type", "unknown"),
                            "required": prop_name in schema.get("required", []),
                            "description": prop_schema.get("description", "")
                        }
                
                endpoint["parameters"].append(param_info)
            
            # Request Body
            rb = op.get("requestBody")
            if rb and "content" in rb:
                for content_type, content_data in rb["content"].items():
                    schema = content_data.get("schema") or {}
                    endpoint["requestBody"] = {
                        "contentType": content_type,
                        "required": rb.get("required", False),
                        "type": schema.get("type", "object"),
                        "description": schema.get("description", "")
                    }
                    break
            
            # Responses
            for status_code, resp in op.get("responses", {}).items():
                response_info = {
                    "description": resp.get("description", ""),
                    "content": {}
                }
                
                for content_type, content_data in resp.get("content", {}).items():
                    schema = content_data.get("schema") or {}
                    example = None
                    if "examples" in content_data and content_data["examples"]:
                        example = next(iter(content_data["examples"].values())).get("value")
                    elif "example" in content_data:
                        example = content_data["example"]
                    
                    response_info["content"][content_type] = {
                        "type": schema.get("type", "object"),
                        "example": example
                    }
                
                endpoint["responses"][status_code] = response_info
            
            api_summary["endpoints"].append(endpoint)
    
    return api_summary

def generate_full_ui_with_azure_openai(api_summary: Dict[str, Any]) -> str:
    """Generate complete integrated UI using Azure OpenAI"""
    
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )
    
    prompt = f"""
You are an expert web developer. Create a complete, fully functional web application with the following requirements:

API Information:
{json.dumps(api_summary, indent=2)}

Requirements:
1. Create a single-page application with HTML, CSS, and JavaScript
2. Build a comprehensive UI that integrates ALL endpoints listed above
3. Include navigation between different API operations
4. Create forms for POST/PUT endpoints with proper validation
5. Display responses in a user-friendly format
6. Handle all parameter types including objects with nested properties
7. Add error handling and loading states
8. Make the UI clean, modern, and responsive
9. Connect all routes and show relationships between endpoints
10. Include a main dashboard/navigation page

Technical Requirements:
- Use vanilla HTML, CSS, and JavaScript (no frameworks)
- Use fetch() for all API calls to {api_summary['baseUrl']}
- Create separate sections/pages for each endpoint
- Add proper form validation for required fields
- Show API responses in formatted JSON or user-friendly cards
- Include navigation menu to switch between different API operations
- Add loading spinners and error messages

Structure:
- Create one complete HTML file with embedded CSS and JavaScript
- Organize the UI with clear sections for each endpoint
- Add a main navigation/dashboard area
- Include breadcrumbs or active state indicators

Please provide the complete, ready-to-use HTML file with embedded CSS and JavaScript.
"""

    try:
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are an expert web developer who creates complete, functional web applications."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=4000
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        print(f"❌ Error calling Azure OpenAI: {e}")
        return None

def save_ui_files(ui_content: str, base_dir: str = "ui"):
    """Save the generated UI content to files"""
    os.makedirs(base_dir, exist_ok=True)
    
    # Save as complete HTML file
    html_file = os.path.join(base_dir, "index.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(ui_content)
    
    print(f"✅ Complete UI saved to {html_file}")
    print(f"🌐 Open {html_file} in your browser to use the application")

if __name__ == "__main__":
    # Check environment variables
    if not all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY]):
        print("❌ Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY environment variables")
        exit(1)
    
    url = input("🔗 Enter Swagger/OpenAPI URL: ").strip()
    
    try:
        # Load and parse swagger
        content = load_from_url(url)
        parsed = parse_swagger(content)
        
        print(f"\n📊 API Title: {parsed['info'].get('title')}")
        print(f"📊 Total Paths: {len(parsed['paths'])}")
        
        # Create purified API summary
        api_summary = create_purified_api_summary(parsed)
        
        print(f"\n🔄 Generating comprehensive UI for all {len(api_summary['endpoints'])} endpoints...")
        
        # Generate complete UI with Azure OpenAI
        ui_content = generate_full_ui_with_azure_openai(api_summary)
        
        if ui_content:
            # Save UI files
            save_ui_files(ui_content)
            
            print("\n✅ UI Generation Complete!")
            print("📁 Files created:")
            print("   - ui/index.html (Complete application)")
            print("\n🚀 Next steps:")
            print("   1. Open ui/index.html in your browser")
            print("   2. Test all API endpoints through the UI")
            print("   3. Ensure your API server is running on the specified endpoint")
        else:
            print("❌ Failed to generate UI content")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
