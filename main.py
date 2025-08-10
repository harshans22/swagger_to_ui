import os
import json
from typing import Any, Dict, Union, List
from datetime import datetime
from dotenv import load_dotenv
import yaml

from parser import load_from_url, SwaggerParser
from core.summary import create_enhanced_api_summary
from core.ui_generation import create_ui_with_langchain
from core.static_ui_builder import write_static_ui

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


# ---------------------- Main Flow ----------------------


def main():
    print("🚀 Advanced Swagger/OpenAPI to UI Generator")
    print("=" * 50)

    source = input("📁 Enter OpenAPI spec URL or file path: ").strip()
    if not source:
        print("❌ No source provided")
        return

    print("\n🎯 Choose UI generation mode:")
    print("1. Semantic App UI (recommended) - Creates contextual domain-specific interface")
    print("2. API Console - Simple testing interface")
    print("3. Deterministic Static - No LLM, basic forms")
    
    mode = input("Select mode (1-3): ").strip()
    
    domain_context = ""
    use_semantic = False
    deterministic = False
    
    if mode == "1":
        use_semantic = True
        domain_context = input("\n💭 Describe your product/domain & desired UX\n(e.g., 'YouTube-like video platform with user channels and subscriptions'): ").strip()
        if not domain_context:
            domain_context = "A modern web application with intuitive user experience"
    elif mode == "2":
        use_semantic = False
        domain_context = input("\n💭 Optional: Brief description of the API purpose: ").strip()
    elif mode == "3":
        deterministic = True
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

        if deterministic:
            print("🔧 Generating deterministic static UI...")
            paths = write_static_ui(api_summary)
            print("✅ Generated files:")
            for name, p in paths.items():
                print(f"   • {name}: {p}")
            return

        use_llm = all([AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY])
        if not use_llm:
            print("❌ Azure OpenAI credentials not found. Use deterministic mode or set env vars.")
            return

        if use_semantic:
            print("🧠 Generating semantic domain-aware UI via LLM...")
        else:
            print("🤖 Generating API console UI via LLM...")
            
        # Update chunker to use semantic analysis if requested
        from core.chunking import APIChunker
        chunker = APIChunker(max_endpoints_per_chunk=6, use_semantic_analysis=use_semantic)
        
        ui_content = create_ui_with_langchain(api_summary, {
            "endpoint": AZURE_OPENAI_ENDPOINT,
            "api_key": AZURE_OPENAI_API_KEY,
            "api_version": AZURE_OPENAI_API_VERSION,
            "deployment": AZURE_OPENAI_DEPLOYMENT
        }, domain_context=domain_context)
        
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
            print("💡 Try using deterministic mode (option 3) or wait a minute before retrying.")
            print("🔧 Consider optimizing your API spec by reducing endpoints or using shorter descriptions.")
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
        print("\n🛠️  Alternative solutions:")
        print("   1. Use deterministic mode (restart and choose option 3)")
        print("   2. Check .env file for correct Azure OpenAI credentials")
        print("   3. Simplify your OpenAPI spec to reduce token usage")
        print("   4. Wait 60 seconds and retry if rate limited")


if __name__ == "__main__":
    main()
