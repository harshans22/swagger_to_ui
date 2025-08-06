import json
from typing import Any, Dict, List, Optional, Union


class SwaggerParser:
    def __init__(self, spec: Dict[str, Any]):
        self.spec = spec

    def _resolve_ref(self, ref: str) -> Dict[str, Any]:
        """Resolve JSON Reference like '#/components/schemas/MySchema'"""
        if not ref.startswith("#/"):
            raise ValueError(f"Only internal refs are supported, but got: {ref}")
        parts = ref.lstrip("#/").split("/")
        current = self.spec
        for part in parts:
            if part not in current:
                raise KeyError(f"Reference path '{ref}' invalid at '{part}'")
            current = current[part]
        return current

    def _extract_schema(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively extract fully expanded schema info"""
        if "$ref" in schema:
            schema = self._resolve_ref(schema["$ref"])

        schema_info = {
            "type": schema.get("type", "object"),
            "format": schema.get("format"),
            "description": schema.get("description", ""),
            "enum": schema.get("enum"),
            "example": schema.get("example"),
            "required": schema.get("required", []),
            "properties": {},
            "items": None,
            "additionalProperties": None,
        }

        # Extract properties for objects
        if schema_info["type"] == "object":
            # Properties
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                schema_info["properties"][prop_name] = self._extract_schema(prop_schema)

            # Additional properties (for free-form objects)
            if "additionalProperties" in schema:
                add_props = schema["additionalProperties"]
                if isinstance(add_props, dict):
                    schema_info["additionalProperties"] = self._extract_schema(add_props)
                else:
                    schema_info["additionalProperties"] = add_props

        # Extract items for arrays
        if schema_info["type"] == "array" and "items" in schema:
            schema_info["items"] = self._extract_schema(schema["items"])

        return schema_info

    def _extract_parameters(self, parameters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract parameters fully resolving refs and schema details"""
        resolved_params = []

        for param in parameters:
            if "$ref" in param:
                param = self._resolve_ref(param["$ref"])

            param_schema = param.get("schema")
            schema_info = self._extract_schema(param_schema) if param_schema else None

            resolved_params.append({
                "name": param.get("name"),
                "in": param.get("in"),  # path, query, header, cookie, body
                "description": param.get("description", ""),
                "required": param.get("required", False) or (param.get("in") == "path"),
                "deprecated": param.get("deprecated", False),
                "schema": schema_info,
                "example": param.get("example"),
                "examples": param.get("examples"),
                "style": param.get("style"),
                "explode": param.get("explode"),
                "allowEmptyValue": param.get("allowEmptyValue")
            })

        return resolved_params

    def _extract_request_body(self, request_body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract requestBody details fully resolving schemas"""
        if "$ref" in request_body:
            request_body = self._resolve_ref(request_body["$ref"])

        content = {}
        for media_type, media_obj in request_body.get("content", {}).items():
            schema = media_obj.get("schema")
            content[media_type] = {
                "schema": self._extract_schema(schema) if schema else None,
                "example": media_obj.get("example"),
                "examples": media_obj.get("examples")
            }

        return {
            "description": request_body.get("description", ""),
            "required": request_body.get("required", False),
            "content": content
        }

    def _extract_responses(self, responses: Dict[str, Any]) -> Dict[str, Any]:
        """Extract responses resolving all refs and schemas"""
        extracted = {}

        for status_code, response in responses.items():
            if "$ref" in response:
                response = self._resolve_ref(response["$ref"])

            content = {}
            for media_type, media_obj in response.get("content", {}).items():
                schema = media_obj.get("schema")
                content[media_type] = {
                    "schema": self._extract_schema(schema) if schema else None,
                    "example": media_obj.get("example"),
                    "examples": media_obj.get("examples")
                }

            extracted[status_code] = {
                "description": response.get("description", ""),
                "headers": response.get("headers", {}),
                "content": content
            }

        return extracted

    def parse(self) -> Dict[str, Any]:
        """Parse entire OpenAPI spec and return detailed structure for UI generation"""
        parsed = {
            "info": self.spec.get("info", {}),
            "servers": self.spec.get("servers", []),
            "tags": self.spec.get("tags", []),
            "paths": {},
            "schemas": {},
            # For extra reusable components if needed later
            "components": self.spec.get("components", {}),
        }

        # Extract components/schemas (fully expanded)
        for name, schema in parsed["components"].get("schemas", {}).items():
            parsed["schemas"][name] = self._extract_schema(schema)

        # Parse paths and operations with full info
        for path, path_item in self.spec.get("paths", {}).items():
            parsed["paths"][path] = {}

            common_parameters = path_item.get("parameters", [])

            for method in ["get", "post", "put", "patch", "delete", "head", "options", "trace"]:
                if method in path_item:
                    operation = path_item[method]
                    op_parameters = common_parameters + operation.get("parameters", [])

                    parsed["paths"][path][method] = {
                        "operationId": operation.get("operationId"),
                        "summary": operation.get("summary", ""),
                        "description": operation.get("description", ""),
                        "tags": operation.get("tags", []),
                        "deprecated": operation.get("deprecated", False),
                        "parameters": self._extract_parameters(op_parameters),
                        "requestBody": self._extract_request_body(operation["requestBody"]) if "requestBody" in operation else None,
                        "responses": self._extract_responses(operation.get("responses", {})),
                        "security": operation.get("security", []),
                        "servers": operation.get("servers", []),
                    }

        return parsed


def parse_swagger(content: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Parse swagger/openapi content string or dict and return parsed detailed dict"""
    if isinstance(content, str):
        content = json.loads(content)
    parser = SwaggerParser(content)
    return parser.parse()