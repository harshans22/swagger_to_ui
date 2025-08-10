from typing import Any, Dict, List

def create_enhanced_api_summary(parsed: Dict[str, Any]) -> Dict[str, Any]:
    endpoints: List[Dict[str, Any]] = []
    for path, operations in parsed.get("paths", {}).items():
        for method, details in operations.items():
            endpoints.append({
                "path": path,
                "method": method.upper(),
                "operationId": details.get("operationId") or f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}",
                "summary": details.get("summary", ""),
                "description": details.get("description", ""),
                "tags": details.get("tags", ["Default"]),
                "deprecated": details.get("deprecated", False),
                "security": details.get("security", []),
                "parameters": details.get("parameters", []),
                "requestBody": details.get("requestBody"),
                "responses": details.get("responses", {}),
                "servers": details.get("servers", [])
            })

    paths_flat = {p: ops for p, ops in parsed.get("paths", {}).items() if ops}

    api_summary: Dict[str, Any] = {
        "openapi": parsed.get("openapi", "3.0.0"),
        "info": parsed.get("info", {}),
        "servers": parsed.get("servers", []),
        "tags": parsed.get("tags", []),
        "paths": paths_flat,
        "schemas": parsed.get("schemas", {}),
        "securitySchemes": parsed.get("securitySchemes", {}),
        "endpoints": endpoints,
        "webhooks": parsed.get("webhooks", {}),
        "totalEndpoints": len(endpoints),
        "methodCounts": {},
        "tagCounts": {},
        "hasAuth": bool(parsed.get("securitySchemes", {})),
        "circularRefs": parsed.get("circularRefs", [])
    }

    for ep in endpoints:
        method = ep["method"]
        api_summary["methodCounts"][method] = api_summary["methodCounts"].get(method, 0) + 1
        for tag in ep["tags"]:
            api_summary["tagCounts"][tag] = api_summary["tagCounts"].get(tag, 0) + 1

    return api_summary
