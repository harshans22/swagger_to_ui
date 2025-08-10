from typing import Any, Dict, List, Optional
from .semantic import SemanticAPIAnalyzer, create_semantic_chunks

class APIChunker:
    """Smart API data chunker that breaks down large APIs into manageable pieces"""

    def __init__(self, max_endpoints_per_chunk: int = 8, use_semantic_analysis: bool = True):
        self.max_endpoints_per_chunk = max_endpoints_per_chunk
        self.use_semantic_analysis = use_semantic_analysis

    def chunk_by_tags(self, api_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Chunk API data by tags/categories or semantic analysis"""
        if self.use_semantic_analysis:
            return self._semantic_chunking(api_summary)
        else:
            return self._tag_based_chunking(api_summary)
    
    def _semantic_chunking(self, api_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use semantic analysis to create meaningful chunks"""
        analyzer = SemanticAPIAnalyzer()
        semantic_model = analyzer.analyze(api_summary)
        
        # Create chunks based on semantic understanding
        chunks = create_semantic_chunks(api_summary, semantic_model, max_resources_per_chunk=3)
        
        # Add global context to each chunk
        for chunk in chunks:
            chunk['semantic_model'] = semantic_model
            chunk['schemas'] = self._extract_relevant_schemas(
                api_summary.get('schemas', {}), 
                chunk.get('endpoints', [])
            )
        
        return chunks
    
    def _tag_based_chunking(self, api_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Original tag-based chunking as fallback"""
        endpoints = api_summary.get("endpoints", [])

        # Group endpoints by tags
        tag_groups: Dict[str, List[Dict[str, Any]]] = {}
        for endpoint in endpoints:
            tags = endpoint.get("tags", ["Default"])
            for tag in tags:
                tag_groups.setdefault(tag, []).append(endpoint)

        # Create chunks from tag groups
        chunks: List[Dict[str, Any]] = []
        for tag, tag_endpoints in tag_groups.items():
            if len(tag_endpoints) > self.max_endpoints_per_chunk:
                # Split by HTTP methods within the tag
                method_groups: Dict[str, List[Dict[str, Any]]] = {}
                for endpoint in tag_endpoints:
                    method = endpoint.get("method", "GET")
                    method_groups.setdefault(method, []).append(endpoint)

                for method, method_endpoints in method_groups.items():
                    for i in range(0, len(method_endpoints), self.max_endpoints_per_chunk):
                        chunk_endpoints = method_endpoints[i:i + self.max_endpoints_per_chunk]
                        chunks.append(self._create_chunk(api_summary, chunk_endpoints, f"{tag}_{method}"))
            else:
                chunks.append(self._create_chunk(api_summary, tag_endpoints, tag))

        return chunks

    def _create_chunk(self, api_summary: Dict[str, Any], endpoints: List[Dict[str, Any]], chunk_name: str) -> Dict[str, Any]:
        """Create a chunk with essential API metadata and specific endpoints"""

        # Extract only relevant schemas for these endpoints
        relevant_schemas = set()
        for endpoint in endpoints:
            # Request body schemas
            req_body = endpoint.get("requestBody")
            if isinstance(req_body, dict) and req_body.get("content"):
                for content_data in req_body["content"].values():
                    schema = content_data.get("schema")
                    if schema:
                        ref = self._extract_schema_ref(schema)
                        if ref:
                            relevant_schemas.add(ref)

            # Response schemas
            responses = endpoint.get("responses", {})
            for response_data in responses.values():
                if isinstance(response_data, dict) and response_data.get("content"):
                    for content_data in response_data["content"].values():
                        schema = content_data.get("schema")
                        if schema:
                            ref = self._extract_schema_ref(schema)
                            if ref:
                                relevant_schemas.add(ref)

        all_schemas = api_summary.get("schemas", {})
        chunk_schemas = {name: schema for name, schema in all_schemas.items() if name in relevant_schemas}

        return {
            "chunk_name": chunk_name,
            "info": api_summary.get("info", {}),
            "servers": api_summary.get("servers", []),
            "securitySchemes": api_summary.get("securitySchemes", {}),
            "endpoints": endpoints,
            "schemas": chunk_schemas,
            "statistics": {
                "totalEndpoints": len(endpoints),
                "hasAuthentication": api_summary.get("hasAuth", False)
            }
        }

    def _extract_relevant_schemas(self, all_schemas: Dict[str, Any], endpoints: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract schemas relevant to the given endpoints"""
        relevant_schemas = set()
        
        for endpoint in endpoints:
            # Request body schemas
            req_body = endpoint.get("requestBody")
            if isinstance(req_body, dict) and req_body.get("content"):
                for content_data in req_body["content"].values():
                    schema = content_data.get("schema")
                    if schema:
                        ref = self._extract_schema_ref(schema)
                        if ref:
                            relevant_schemas.add(ref)

            # Response schemas
            responses = endpoint.get("responses", {})
            for response_data in responses.values():
                if isinstance(response_data, dict) and response_data.get("content"):
                    for content_data in response_data["content"].values():
                        schema = content_data.get("schema")
                        if schema:
                            ref = self._extract_schema_ref(schema)
                            if ref:
                                relevant_schemas.add(ref)
        
        return {name: schema for name, schema in all_schemas.items() if name in relevant_schemas}

    def _extract_schema_ref(self, schema: Any) -> Optional[str]:
        if isinstance(schema, dict):
            ref = schema.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                return ref.split("/")[-1]
            items = schema.get("items")
            if isinstance(items, dict):
                return self._extract_schema_ref(items)
        return None
