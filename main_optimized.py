import os
import json
import asyncio
from typing import Any, Dict, Union, List
from datetime import datetime
from dotenv import load_dotenv
import yaml

from parser import load_from_url, SwaggerParser
from core.summary import create_enhanced_api_summary
from core.ui_generation import create_ui_with_langchain, create_ui_with_advanced_processing

load_dotenv()

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

# ---------------------- Loading & Parsing ----------------------


def load_openapi_spec(source: str) -> Union[str, Dict[str, Any]]:
    """Load OpenAPI specification from URL or file path"""
    if source.startswith(("http://", "https://")):
        return load_from_url(source)
    with open(source, "r", encoding="utf-8") as f:
        content = f.read()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return yaml.safe_load(content)


def detect_openapi_version(content: Union[str, Dict[str, Any]]) -> str:
    """Detect OpenAPI version from content"""
    if isinstance(content, str):
        try:
            spec = json.loads(content)
        except json.JSONDecodeError:
            spec = yaml.safe_load(content)
    else:
        spec = content
    return spec.get("openapi") or spec.get("swagger") or "unknown"


# ---------------------- Validation & Reporting ----------------------


def validate_openapi_spec(spec: Dict[str, Any]) -> List[str]:
    """Validate OpenAPI specification and return warnings"""
    warnings: List[str] = []
    if "info" not in spec:
        warnings.append("Missing 'info' section")
    else:
        if "title" not in spec["info"]:
            warnings.append("Missing 'info.title'")
    if not spec.get("paths"):
        warnings.append("No paths defined")
    for path, methods in spec.get("paths", {}).items():
        for method, operation in methods.items():
            if isinstance(operation, dict) and operation.get("deprecated"):
                warnings.append(f"Deprecated endpoint: {method.upper()} {path}")
    return warnings


# ---------------------- UI Saving ----------------------


def save_ui_files(ui_content: str, base_dir: str = "ui") -> str:
    """Save the generated UI file only"""
    os.makedirs(base_dir, exist_ok=True)
    html_file = os.path.join(base_dir, "index.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(ui_content)
    return html_file


# ---------------------- Async Main Flow ----------------------


async def async_main():
    """Async main function to support parallel processing"""
    print("🚀 Advanced Swagger/OpenAPI to UI Generator")
    print("=" * 50)

    source = input("📁 Enter OpenAPI spec URL or file path: ").strip()
    if not source:
        print("❌ No source provided")
        return

    print("\n🚀 Choose UI Generation Mode:")
    print("1. 🧠 Semantic Domain-Aware UI (Recommended)")
    print("   → Creates application-specific interfaces (e.g., YouTube-like platform)")
    print("   → Uses AI to understand your domain and build intuitive workflows")
    print("2. 🤖 API Console UI") 
    print("   → Interactive testing interface for developers")
    print("   → Clean, professional API documentation and testing tools")
    
    print("\n⚡ Performance Options:")
    print("A. 🚀 Advanced Parallel Processing (3-5x faster, recommended)")
    print("B. 🔄 Sequential Processing (legacy mode)")
    
    mode = input("\nSelect UI mode (1-2): ").strip()
    performance_mode = input("Select performance mode (A/B): ").strip().upper()
    
    use_parallel = performance_mode == "A" or performance_mode == ""  # Default to parallel
    
    domain_context = ""
    use_semantic = False
    
    if mode == "1":
        use_semantic = True
        domain_context = input("\n💭 Describe your product/domain & desired UX\n(e.g., 'YouTube-like video platform with user channels and subscriptions'): ").strip()
        if not domain_context:
            domain_context = "A modern web application with intuitive user experience"
    elif mode == "2":
        use_semantic = False
        domain_context = input("\n💭 Optional: Brief description of the API purpose: ").strip()
    else:
        print("❌ Invalid mode, using semantic mode")
        use_semantic = True

    try:
        print(f"\n📥 Loading spec from: {source}")
        content = load_openapi_spec(source)
        version = detect_openapi_version(content)
        print(f"📋 Detected OpenAPI version: {version}")

        if isinstance(content, str):
            try:
                spec_dict = json.loads(content)
            except json.JSONDecodeError:
                spec_dict = yaml.safe_load(content)
        else:
            spec_dict = content

        warnings = validate_openapi_spec(spec_dict)
        if warnings:
            print("⚠️  Specification warnings:")
            for w in warnings[:5]:
                print(f"   • {w}")
            if len(warnings) > 5:
                print(f"   ... and {len(warnings) - 5} more warnings")

        print("⚙️  Parsing specification...")
        parser = SwaggerParser(spec_dict if isinstance(spec_dict, dict) else json.loads(spec_dict))
        parsed = parser.parse()
        print(f"✅ Parsed {len(parsed.get('paths', {}))} paths")

        print("📊 Building API summary...")
        api_summary = create_enhanced_api_summary(parsed)
        print(f"📈 Total endpoints: {api_summary['totalEndpoints']}")

        use_llm = all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY])
        if not use_llm:
            print("❌ Azure OpenAI credentials not found. Please set your environment variables.")
            print("Required: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY")
            return

        azure_config = {
            "endpoint": AZURE_OPENAI_ENDPOINT,
            "api_key": AZURE_OPENAI_API_KEY,
            "api_version": AZURE_OPENAI_API_VERSION,
            "deployment": AZURE_OPENAI_DEPLOYMENT
        }

        if use_parallel:
            print("🚀 Starting advanced parallel processing...")
            ui_content = await create_ui_with_advanced_processing(
                api_summary=api_summary,
                azure_config=azure_config,
                domain_context=domain_context,
                use_parallel_processing=True,
                use_semantic_grouping=use_semantic
            )
        else:
            if use_semantic:
                print("🧠 Generating semantic domain-aware UI via sequential LLM...")
            else:
                print("🤖 Generating API console UI via sequential LLM...")
                
            ui_content = create_ui_with_langchain(
                api_summary, azure_config, domain_context=domain_context
            )
        
        if not ui_content:
            print("❌ Failed to generate UI")
            return

        path = save_ui_files(ui_content)
        print(f"\n🎉 UI Generation Complete!")
        print(f"📁 File created: {path}")
        print(f"🌐 Open {path} in your browser to use your application!")
        
        # Optionally open in browser
        try:
            import webbrowser
            open_browser = input("\n🚀 Open in browser now? (y/N): ").strip().lower()
            if open_browser in ['y', 'yes']:
                webbrowser.open(f"file://{os.path.abspath(path)}")
        except:
            pass
            
    except Exception as e:
        error_message = str(e)
        
        # Handle specific Azure OpenAI errors
        if "429" in error_message or "rate limit" in error_message.lower():
            print("⏰ Azure OpenAI rate limit reached.")
            print("💡 Try waiting a minute before retrying, or simplify your API specification.")
            print("🔧 Consider reducing the number of endpoints or using shorter descriptions.")
        elif "connection" in error_message.lower() or "timeout" in error_message.lower():
            print("🌐 Connection issue with Azure OpenAI service.")
            print("💡 Check your internet connection and Azure OpenAI endpoint configuration.")
        elif "authentication" in error_message.lower() or "401" in error_message:
            print("🔑 Authentication failed with Azure OpenAI.")
            print("💡 Check your AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT in .env file.")
        else:
            print(f"❌ Error: {e}")
            
        print("\n📋 Full error trace:")
        import traceback
        traceback.print_exc()
        
        # Suggest alternatives
        print("\n🛠️  Solutions to try:")
        print("   1. Wait 60 seconds and retry if rate limited")
        print("   2. Check .env file for correct Azure OpenAI credentials")
        print("   3. Simplify your OpenAPI spec to reduce complexity")
        print("   4. Ensure your API endpoints are properly formatted")


def main():
    """Main entry point - runs async main"""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n⚠️ Generation cancelled by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
