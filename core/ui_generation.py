import json
from typing import Any, Dict, Optional
import time
import random
from langchain.schema import HumanMessage
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .chunking import APIChunker


def retry_with_backoff(func, max_retries=3, base_delay=60):
    """Retry function with exponential backoff for rate limits"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "rate limit" in error_msg:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 5)
                    print(f"⏰ Rate limited. Waiting {delay:.1f}s before retry {attempt + 2}/{max_retries}...")
                    time.sleep(delay)
                    continue
            raise e
    return None


def create_ui_with_langchain(api_summary: dict, azure_config: dict, domain_context: str = None) -> str:
    """Create UI using LangChain with optimized token usage.

    azure_config expects keys: endpoint, api_key, api_version, deployment
    domain_context: optional high-level user description of the product / business domain and UI goals.
    """
    # Build a compact global catalog (reduced size)
    catalog_lines = []
    for ep in api_summary.get("endpoints", [])[:50]:  # Reduced from 200 to 50
        method = ep['method']
        path = ep['path']
        summary = (ep.get('summary', '') or '')[:60]  # Truncate summaries
        catalog_lines.append(f"{method} {path} - {summary}")
    global_catalog = "\n".join(catalog_lines)

    llm = AzureChatOpenAI(
        azure_endpoint=azure_config["endpoint"],
        api_key=azure_config["api_key"],
        api_version=azure_config["api_version"],
        deployment_name=azure_config["deployment"],
        temperature=0.1,  # Reduced from 0.15 for more deterministic output
        max_tokens=8000   # Reduced from 15000
    )

    # Use smaller chunks and semantic analysis
    chunker = APIChunker(max_endpoints_per_chunk=4, use_semantic_analysis=True)  # Reduced from 6 to 4
    chunks = chunker.chunk_by_tags(api_summary)
    print(f"📦 Split API into {len(chunks)} optimized chunks for token efficiency")

    # Estimate token usage
    estimated_tokens = len(chunks) * 3000  # Rough estimate
    print(f"💭 Estimated token usage: ~{estimated_tokens:,} tokens")
    if estimated_tokens > 50000:
        print("⚠️  High token usage detected. Consider using deterministic mode for large APIs.")

    # Highly optimized base template - focus on essentials only
    base_template = PromptTemplate(
        input_variables=["endpoints", "domain_context", "total_chunks"],
        template=(
            "Build a complete web app (single HTML file) for this API domain: {domain_context}\n\n"
            "ENDPOINTS ({total_chunks} chunks total):\n{endpoints}\n\n"
            "Requirements:\n"
            "1. Complete HTML with embedded CSS/JS\n"
            "2. Sidebar navigation for main resources\n"
            "3. List/detail/create pages for each resource\n"
            "4. Authentication handling if auth endpoints exist\n"
            "5. Search functionality\n"
            "6. Responsive design\n"
            "7. Real API integration with fetch()\n"
            "8. Comments for extension points\n\n"
            "Return only the HTML code:" )
    )

    # Minimal extension template
    extension_template = PromptTemplate(
        input_variables=["endpoints", "chunk_number"],
        template=(
            "Add these endpoints to existing app (chunk {chunk_number}):\n{endpoints}\n\n"
            "Return only the additional HTML sections to insert:\n"
            "<!-- NAV-ADD --> navigation items\n"
            "<!-- PAGES-ADD --> new page content\n"
            "<!-- SCRIPT-ADD --> new JavaScript functions" )
    )

    output_parser = StrOutputParser()

    try:
        # Process first chunk with minimal data
        first_chunk = chunks[0]
        print(f"🎨 Generating base UI from chunk 1/{len(chunks)}...")
        
        # Extract only essential endpoint data
        essential_endpoints = []
        for ep in first_chunk.get('endpoints', []):
            essential_endpoints.append({
                'method': ep['method'],
                'path': ep['path'],
                'summary': (ep.get('summary', '') or '')[:50],
                'hasAuth': bool(ep.get('security')),
                'hasBody': bool(ep.get('requestBody'))
            })

        base_chain = base_template | llm | output_parser
        
        def invoke_base_chain():
            return base_chain.invoke({
                "endpoints": json.dumps(essential_endpoints, indent=1),
                "domain_context": (domain_context or "Generic API application")[:200],  # Limit context
                "total_chunks": len(chunks)
            })
        
        base_response = retry_with_backoff(invoke_base_chain)
        complete_ui = base_response

        # Process remaining chunks with minimal extensions
        extension_chain = extension_template | llm | output_parser
        for i, chunk in enumerate(chunks[1:], 2):
            print(f"🔧 Extending UI with chunk {i}/{len(chunks)}...")
            
            # Only send essential data for extensions
            essential_endpoints = []
            for ep in chunk.get('endpoints', [])[:3]:  # Limit to 3 endpoints per extension
                essential_endpoints.append({
                    'method': ep['method'],
                    'path': ep['path'],
                    'summary': (ep.get('summary', '') or '')[:30]
                })

            def invoke_extension_chain():
                return extension_chain.invoke({
                    "endpoints": json.dumps(essential_endpoints, indent=1),
                    "chunk_number": i
                })

            extension_response = retry_with_backoff(invoke_extension_chain)
            complete_ui = merge_ui_extensions_optimized(complete_ui, extension_response)
        
        return complete_ui
    except Exception as e:
        print(f"LangChain UI creation error: {e}")
        return None


def merge_ui_extensions_optimized(base_ui: str, extension: str) -> str:
    """Optimized merge using simple pattern matching"""
    if not extension:
        return base_ui
    
    lines = extension.split('\n')
    nav_content = ""
    pages_content = ""
    script_content = ""
    
    current_section = None
    
    for line in lines:
        if "<!-- NAV-ADD -->" in line:
            current_section = "nav"
        elif "<!-- PAGES-ADD -->" in line:
            current_section = "pages"
        elif "<!-- SCRIPT-ADD -->" in line:
            current_section = "script"
        elif line.strip().startswith('<!--'):
            current_section = None
        elif current_section == "nav":
            nav_content += line + "\n"
        elif current_section == "pages":
            pages_content += line + "\n"
        elif current_section == "script":
            script_content += line + "\n"
    
    result = base_ui
    
    # Simple insertion points
    if nav_content and "</nav>" in result:
        result = result.replace("</nav>", nav_content + "</nav>")
    
    if pages_content and "</main>" in result:
        result = result.replace("</main>", pages_content + "</main>")
    
    if script_content and "</script>" in result:
        result = result.replace("</script>", script_content + "\n</script>")
    
    return result


def merge_ui_extensions(base_ui: str, extension: str) -> str:
    if not extension or "INSERT" not in extension:
        return base_ui

    lines = extension.split('\n')
    nav_items, forms, scripts = [], [], []
    current_section = None
    current_content = []

    for line in lines:
        if "INSERT NEW NAV ITEMS" in line:
            current_section = "nav"; current_content = []
        elif "INSERT NEW FORMS" in line:
            current_section = "forms"; current_content = []
        elif "INSERT NEW SCRIPTS" in line:
            current_section = "scripts"; current_content = []
        elif line.strip().startswith('<!--') and "INSERT" in line:
            if current_section == "nav": nav_items.extend(current_content)
            elif current_section == "forms": forms.extend(current_content)
            elif current_section == "scripts": scripts.extend(current_content)
            current_content = []
        else:
            if current_section: current_content.append(line)

    if current_section == "nav": nav_items.extend(current_content)
    elif current_section == "forms": forms.extend(current_content)
    elif current_section == "scripts": scripts.extend(current_content)

    result = base_ui
    if nav_items:
        nav_content = '\n'.join(nav_items)
        nav_end = result.find('</nav>')
        if nav_end > 0:
            result = result[:nav_end] + nav_content + '\n' + result[nav_end:]
    if forms:
        form_content = '\n'.join(forms)
        main_end = result.find('</main>')
        if main_end > 0:
            result = result[:main_end] + form_content + '\n' + result[main_end:]
        else:
            body_end = result.rfind('</body>')
            if body_end > 0:
                result = result[:body_end] + '<div class="additional-endpoints">' + form_content + '</div>\n' + result[body_end:]
    if scripts:
        script_content = '\n'.join(scripts)
        script_end = result.rfind('</script>')
        if script_end > 0:
            script_start = result.rfind('<script', 0, script_end)
            if script_start > 0:
                result = result[:script_end] + '\n' + script_content + '\n' + result[script_end:]
        else:
            body_end = result.rfind('</body>')
            if body_end > 0:
                result = result[:body_end] + '<script>\n' + script_content + '\n</script>\n' + result[body_end:]
    return result
