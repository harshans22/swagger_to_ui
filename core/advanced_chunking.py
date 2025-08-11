"""
Advanced Intelligent Chunking Strategy with Token-Aware Processing
Implements dynamic chunk sizing, complexity scoring, and real-time token counting
"""

import tiktoken
import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import math


@dataclass
class EndpointComplexity:
    """Represents complexity metrics for an API endpoint"""
    endpoint_data: Dict[str, Any]
    token_count: int
    complexity_score: float
    semantic_weight: float = 1.0
    priority: int = 1  # 1=high, 2=medium, 3=low


@dataclass
class IntelligentChunk:
    """Enhanced chunk with token awareness and complexity balancing"""
    chunk_id: str
    endpoints: List[EndpointComplexity]
    estimated_tokens: int
    complexity_distribution: Dict[str, int] = field(default_factory=dict)
    semantic_coherence: float = 0.0
    processing_priority: int = 1
    
    @property
    def endpoint_count(self) -> int:
        return len(self.endpoints)
    
    @property
    def average_complexity(self) -> float:
        if not self.endpoints:
            return 0.0
        return sum(ep.complexity_score for ep in self.endpoints) / len(self.endpoints)


class AdvancedAPIChunker:
    """
    Intelligent chunking system with token-aware processing and complexity scoring
    
    Features:
    - Dynamic chunk sizing based on token estimation using tiktoken
    - Semantic grouping by API tags/categories for better UI coherence  
    - Complexity scoring to balance simple and complex endpoints within chunks
    - Real-time token counting for optimal LLM context usage
    """
    
    def __init__(
        self,
        target_tokens_per_chunk: int = 12000,  # Optimal for GPT-4 context
        max_tokens_per_chunk: int = 15000,     # Hard limit
        min_endpoints_per_chunk: int = 2,
        max_endpoints_per_chunk: int = 12,
        encoding_model: str = "gpt-4"
    ):
        self.target_tokens_per_chunk = target_tokens_per_chunk
        self.max_tokens_per_chunk = max_tokens_per_chunk
        self.min_endpoints_per_chunk = min_endpoints_per_chunk
        self.max_endpoints_per_chunk = max_endpoints_per_chunk
        
        # Initialize tiktoken encoder for accurate token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model(encoding_model)
        except KeyError:
            # Fallback to cl100k_base if model not found
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
            
        # Complexity weights for different API elements
        self.complexity_weights = {
            'path_params': 1.2,
            'query_params': 1.0,
            'request_body': 2.0,
            'response_schemas': 1.5,
            'security_requirements': 1.3,
            'nested_objects': 2.5,
            'array_fields': 1.8,
            'enum_fields': 1.1
        }

    def count_tokens(self, text: str) -> int:
        """Accurately count tokens using tiktoken"""
        if not text:
            return 0
        try:
            return len(self.tokenizer.encode(str(text)))
        except Exception:
            # Fallback to rough estimation if encoding fails
            return len(str(text)) // 4

    def calculate_endpoint_complexity(self, endpoint: Dict[str, Any]) -> float:
        """
        Calculate complexity score for an endpoint based on multiple factors
        Returns score from 1.0 (simple) to 10.0 (very complex)
        """
        complexity = 1.0
        
        # Path complexity (parameters, nesting)
        path = endpoint.get('path', '')
        path_params = path.count('{')
        complexity += path_params * self.complexity_weights['path_params']
        complexity += path.count('/') * 0.2  # Path depth
        
        # Parameter complexity
        parameters = endpoint.get('parameters', [])
        query_params = sum(1 for p in parameters if p.get('in') == 'query')
        complexity += query_params * self.complexity_weights['query_params']
        
        # Request body complexity
        request_body = endpoint.get('requestBody', {})
        if request_body:
            complexity += self.complexity_weights['request_body']
            content = request_body.get('content', {})
            for media_type, schema_info in content.items():
                complexity += self._analyze_schema_complexity(schema_info.get('schema', {}))
        
        # Response complexity
        responses = endpoint.get('responses', {})
        for status_code, response_data in responses.items():
            if isinstance(response_data, dict):
                content = response_data.get('content', {})
                for media_type, schema_info in content.items():
                    complexity += self._analyze_schema_complexity(schema_info.get('schema', {})) * 0.8
        
        # Security requirements
        security = endpoint.get('security', [])
        if security:
            complexity += len(security) * self.complexity_weights['security_requirements']
        
        # Cap complexity at reasonable maximum
        return min(complexity, 10.0)

    def _analyze_schema_complexity(self, schema: Dict[str, Any]) -> float:
        """Analyze schema complexity recursively"""
        if not isinstance(schema, dict):
            return 0.0
        
        complexity = 0.0
        
        # Object complexity
        properties = schema.get('properties', {})
        complexity += len(properties) * 0.3
        
        # Array complexity
        if schema.get('type') == 'array':
            complexity += self.complexity_weights['array_fields']
            items = schema.get('items', {})
            complexity += self._analyze_schema_complexity(items) * 0.7
        
        # Nested object complexity
        for prop_name, prop_schema in properties.items():
            if isinstance(prop_schema, dict):
                if prop_schema.get('type') == 'object':
                    complexity += self.complexity_weights['nested_objects']
                    complexity += self._analyze_schema_complexity(prop_schema) * 0.6
                elif 'enum' in prop_schema:
                    complexity += self.complexity_weights['enum_fields']
        
        # Reference complexity
        if '$ref' in schema:
            complexity += 1.5  # Referenced schemas add complexity
        
        return complexity

    def analyze_endpoints(self, api_summary: Dict[str, Any]) -> List[EndpointComplexity]:
        """Analyze all endpoints and calculate complexity metrics"""
        endpoints = api_summary.get('endpoints', [])
        analyzed_endpoints = []
        
        for endpoint in endpoints:
            # Calculate complexity score
            complexity = self.calculate_endpoint_complexity(endpoint)
            
            # Count tokens for this endpoint
            endpoint_json = json.dumps(endpoint, indent=2)
            token_count = self.count_tokens(endpoint_json)
            
            # Determine semantic weight based on tags
            tags = endpoint.get('tags', ['default'])
            semantic_weight = self._calculate_semantic_weight(tags)
            
            # Assign priority based on HTTP method and complexity
            priority = self._assign_priority(endpoint, complexity)
            
            analyzed_endpoints.append(EndpointComplexity(
                endpoint_data=endpoint,
                token_count=token_count,
                complexity_score=complexity,
                semantic_weight=semantic_weight,
                priority=priority
            ))
        
        return analyzed_endpoints

    def _calculate_semantic_weight(self, tags: List[str]) -> float:
        """Calculate semantic weight based on endpoint tags"""
        # Higher weight for core/important functionality
        important_tags = {
            'auth', 'authentication', 'user', 'users', 'login', 'core', 
            'main', 'primary', 'essential', 'account', 'profile'
        }
        
        weight = 1.0
        for tag in tags:
            tag_lower = tag.lower()
            if any(important in tag_lower for important in important_tags):
                weight += 0.5
        
        return min(weight, 2.0)  # Cap at 2.0

    def _assign_priority(self, endpoint: Dict[str, Any], complexity: float) -> int:
        """Assign processing priority (1=high, 2=medium, 3=low)"""
        method = endpoint.get('method', '').upper()
        
        # High priority: CRUD operations and auth
        if method in ['GET', 'POST'] or complexity < 3.0:
            return 1
        
        # Medium priority: Updates and moderate complexity
        if method in ['PUT', 'PATCH'] or complexity < 6.0:
            return 2
        
        # Low priority: Complex operations
        return 3

    def create_intelligent_chunks(
        self, 
        api_summary: Dict[str, Any],
        use_semantic_grouping: bool = True
    ) -> List[IntelligentChunk]:
        """
        Create optimized chunks with token awareness and complexity balancing
        """
        print("🧠 Analyzing endpoint complexity and token requirements...")
        
        # Analyze all endpoints
        analyzed_endpoints = self.analyze_endpoints(api_summary)
        
        print(f"📊 Analyzed {len(analyzed_endpoints)} endpoints")
        print(f"📈 Average complexity: {sum(ep.complexity_score for ep in analyzed_endpoints) / len(analyzed_endpoints):.2f}")
        
        if use_semantic_grouping:
            # Group by semantic similarity (tags)
            semantic_groups = self._group_by_semantics(analyzed_endpoints)
            chunks = []
            
            for group_name, endpoints in semantic_groups.items():
                group_chunks = self._create_balanced_chunks(endpoints, group_name)
                chunks.extend(group_chunks)
        else:
            # Create chunks based on complexity and token limits
            chunks = self._create_balanced_chunks(analyzed_endpoints, "mixed")
        
        # Optimize chunk distribution
        optimized_chunks = self._optimize_chunk_distribution(chunks)
        
        print(f"✅ Created {len(optimized_chunks)} optimized chunks")
        for i, chunk in enumerate(optimized_chunks):
            print(f"   Chunk {i+1}: {chunk.endpoint_count} endpoints, "
                  f"~{chunk.estimated_tokens} tokens, "
                  f"avg complexity: {chunk.average_complexity:.2f}")
        
        return optimized_chunks

    def _group_by_semantics(self, endpoints: List[EndpointComplexity]) -> Dict[str, List[EndpointComplexity]]:
        """Group endpoints by semantic similarity using tags"""
        groups = defaultdict(list)
        
        for endpoint in endpoints:
            tags = endpoint.endpoint_data.get('tags', ['default'])
            # Use the first tag as primary grouping
            primary_tag = tags[0] if tags else 'default'
            groups[primary_tag].append(endpoint)
        
        return dict(groups)

    def _create_balanced_chunks(
        self, 
        endpoints: List[EndpointComplexity], 
        group_name: str
    ) -> List[IntelligentChunk]:
        """Create balanced chunks within a semantic group"""
        if not endpoints:
            return []
        
        # Sort by priority and complexity for optimal distribution
        sorted_endpoints = sorted(
            endpoints, 
            key=lambda ep: (ep.priority, -ep.complexity_score)
        )
        
        chunks = []
        current_chunk_endpoints = []
        current_tokens = 0
        chunk_counter = 0
        
        for endpoint in sorted_endpoints:
            # Check if adding this endpoint would exceed limits
            projected_tokens = current_tokens + endpoint.token_count
            
            should_create_new_chunk = (
                # Token limit exceeded
                projected_tokens > self.max_tokens_per_chunk or
                # Target reached and minimum endpoints met
                (projected_tokens > self.target_tokens_per_chunk and 
                 len(current_chunk_endpoints) >= self.min_endpoints_per_chunk) or
                # Maximum endpoints reached
                len(current_chunk_endpoints) >= self.max_endpoints_per_chunk
            )
            
            if should_create_new_chunk and current_chunk_endpoints:
                # Create chunk from current endpoints
                chunk_id = f"{group_name}_{chunk_counter}"
                chunks.append(self._build_chunk(chunk_id, current_chunk_endpoints, current_tokens))
                
                # Reset for new chunk
                current_chunk_endpoints = []
                current_tokens = 0
                chunk_counter += 1
            
            # Add endpoint to current chunk
            current_chunk_endpoints.append(endpoint)
            current_tokens += endpoint.token_count
        
        # Create final chunk if there are remaining endpoints
        if current_chunk_endpoints:
            chunk_id = f"{group_name}_{chunk_counter}"
            chunks.append(self._build_chunk(chunk_id, current_chunk_endpoints, current_tokens))
        
        return chunks

    def _build_chunk(
        self, 
        chunk_id: str, 
        endpoints: List[EndpointComplexity], 
        estimated_tokens: int
    ) -> IntelligentChunk:
        """Build an IntelligentChunk with complexity analysis"""
        
        # Analyze complexity distribution
        complexity_distribution = {
            'simple': sum(1 for ep in endpoints if ep.complexity_score < 3.0),
            'moderate': sum(1 for ep in endpoints if 3.0 <= ep.complexity_score < 6.0),
            'complex': sum(1 for ep in endpoints if ep.complexity_score >= 6.0)
        }
        
        # Calculate semantic coherence (higher if endpoints share tags)
        all_tags = []
        for ep in endpoints:
            all_tags.extend(ep.endpoint_data.get('tags', []))
        
        unique_tags = set(all_tags)
        semantic_coherence = len(all_tags) / len(unique_tags) if unique_tags else 1.0
        
        # Determine processing priority (highest priority endpoint wins)
        processing_priority = min(ep.priority for ep in endpoints)
        
        return IntelligentChunk(
            chunk_id=chunk_id,
            endpoints=endpoints,
            estimated_tokens=estimated_tokens,
            complexity_distribution=complexity_distribution,
            semantic_coherence=semantic_coherence,
            processing_priority=processing_priority
        )

    def _optimize_chunk_distribution(self, chunks: List[IntelligentChunk]) -> List[IntelligentChunk]:
        """Optimize chunk distribution for better load balancing"""
        if len(chunks) <= 1:
            return chunks
        
        # Sort chunks by processing priority and estimated processing time
        sorted_chunks = sorted(
            chunks, 
            key=lambda c: (c.processing_priority, -c.estimated_tokens)
        )
        
        # Try to balance extremely large chunks
        optimized_chunks = []
        for chunk in sorted_chunks:
            if (chunk.estimated_tokens > self.max_tokens_per_chunk * 0.9 and 
                chunk.endpoint_count > self.min_endpoints_per_chunk * 2):
                # Split large chunk
                split_chunks = self._split_large_chunk(chunk)
                optimized_chunks.extend(split_chunks)
            else:
                optimized_chunks.append(chunk)
        
        return optimized_chunks

    def _split_large_chunk(self, large_chunk: IntelligentChunk) -> List[IntelligentChunk]:
        """Split a large chunk into smaller, balanced chunks"""
        endpoints = large_chunk.endpoints
        mid_point = len(endpoints) // 2
        
        # Split at the midpoint, trying to maintain semantic coherence
        chunk1_endpoints = endpoints[:mid_point]
        chunk2_endpoints = endpoints[mid_point:]
        
        chunk1_tokens = sum(ep.token_count for ep in chunk1_endpoints)
        chunk2_tokens = sum(ep.token_count for ep in chunk2_endpoints)
        
        chunk1 = self._build_chunk(
            f"{large_chunk.chunk_id}_part1",
            chunk1_endpoints,
            chunk1_tokens
        )
        
        chunk2 = self._build_chunk(
            f"{large_chunk.chunk_id}_part2", 
            chunk2_endpoints,
            chunk2_tokens
        )
        
        return [chunk1, chunk2]

    def convert_to_legacy_format(self, intelligent_chunks: List[IntelligentChunk]) -> List[Dict[str, Any]]:
        """Convert IntelligentChunks to legacy format for backward compatibility"""
        legacy_chunks = []
        
        for chunk in intelligent_chunks:
            # Extract endpoint data
            endpoints_data = [ep.endpoint_data for ep in chunk.endpoints]
            
            # Create legacy chunk format
            legacy_chunk = {
                "chunk_name": chunk.chunk_id,
                "endpoints": endpoints_data,
                "statistics": {
                    "totalEndpoints": chunk.endpoint_count,
                    "estimatedTokens": chunk.estimated_tokens,
                    "averageComplexity": chunk.average_complexity,
                    "complexityDistribution": chunk.complexity_distribution,
                    "semanticCoherence": chunk.semantic_coherence,
                    "processingPriority": chunk.processing_priority
                }
            }
            
            legacy_chunks.append(legacy_chunk)
        
        return legacy_chunks


# Async utilities for future parallel processing
async def async_chunk_analysis(chunker: AdvancedAPIChunker, api_summary: Dict[str, Any]) -> List[IntelligentChunk]:
    """Async wrapper for chunk analysis"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, chunker.create_intelligent_chunks, api_summary)
