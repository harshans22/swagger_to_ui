from typing import Dict, Any, List, Set, Optional
import re
from collections import defaultdict

class SemanticAPIAnalyzer:
    """Analyzes API structure to understand domain resources, relationships, and user flows"""
    
    def __init__(self):
        self.resources = {}
        self.relationships = {}
        self.auth_endpoints = []
        self.media_endpoints = []
        self.analytics_endpoints = []
        self.search_endpoints = []
        self.action_endpoints = []
        
    def analyze(self, api_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Perform comprehensive semantic analysis of the API"""
        endpoints = api_summary.get('endpoints', [])
        schemas = api_summary.get('schemas', {})
        
        # Step 1: Extract resources and group operations
        self._extract_resources(endpoints)
        
        # Step 2: Analyze schemas for field types and relationships
        self._analyze_schemas(schemas)
        
        # Step 3: Detect special endpoint patterns
        self._detect_special_endpoints(endpoints)
        
        # Step 4: Build relationships between resources
        self._build_relationships(endpoints, schemas)
        
        # Step 5: Infer user journeys and workflows
        workflows = self._infer_workflows()
        
        return {
            'resources': self.resources,
            'relationships': self.relationships,
            'auth': {
                'endpoints': self.auth_endpoints,
                'required': len(self.auth_endpoints) > 0
            },
            'media': {
                'endpoints': self.media_endpoints,
                'hasUpload': any(ep.get('hasFileUpload') for ep in self.media_endpoints),
                'hasStreaming': any(ep.get('hasStreaming') for ep in self.media_endpoints)
            },
            'analytics': self.analytics_endpoints,
            'search': self.search_endpoints,
            'actions': self.action_endpoints,
            'workflows': workflows,
            'navigation_structure': self._build_navigation_structure()
        }
    
    def _extract_resources(self, endpoints: List[Dict[str, Any]]):
        """Extract domain resources from endpoint paths"""
        for endpoint in endpoints:
            path = endpoint.get('path', '')
            method = endpoint.get('method', '').upper()
            
            # Extract resource name from path (first meaningful segment)
            path_segments = [s for s in path.split('/') if s and not s.startswith('{')]
            if not path_segments:
                continue
                
            # Skip common prefixes
            if path_segments[0] in ['api', 'v1', 'v2', 'v3']:
                path_segments = path_segments[1:]
            
            if not path_segments:
                continue
                
            resource_name = path_segments[0]
            
            # Initialize resource if not exists
            if resource_name not in self.resources:
                self.resources[resource_name] = {
                    'name': resource_name,
                    'displayName': self._humanize_name(resource_name),
                    'operations': {},
                    'fields': set(),
                    'primaryKey': 'id',
                    'supports': {
                        'list': False,
                        'detail': False,
                        'create': False,
                        'update': False,
                        'delete': False,
                        'search': False,
                        'pagination': False
                    },
                    'listEndpoint': None,
                    'detailEndpoint': None,
                    'createEndpoint': None,
                    'updateEndpoint': None,
                    'deleteEndpoint': None,
                    'actions': []
                }
            
            resource = self.resources[resource_name]
            
            # Classify operation type
            operation_type = self._classify_operation(path, method, endpoint)
            resource['operations'][f"{method}:{path}"] = {
                'endpoint': endpoint,
                'type': operation_type,
                'method': method,
                'path': path
            }
            
            # Update capabilities
            if operation_type == 'list':
                resource['supports']['list'] = True
                resource['listEndpoint'] = endpoint
                self._detect_pagination_and_search(endpoint, resource)
            elif operation_type == 'detail':
                resource['supports']['detail'] = True
                resource['detailEndpoint'] = endpoint
            elif operation_type == 'create':
                resource['supports']['create'] = True
                resource['createEndpoint'] = endpoint
            elif operation_type == 'update':
                resource['supports']['update'] = True
                resource['updateEndpoint'] = endpoint
            elif operation_type == 'delete':
                resource['supports']['delete'] = True
                resource['deleteEndpoint'] = endpoint
            elif operation_type == 'action':
                resource['actions'].append(endpoint)
    
    def _classify_operation(self, path: str, method: str, endpoint: Dict[str, Any]) -> str:
        """Classify what type of operation this endpoint represents"""
        has_id_param = '{id}' in path or '{' in path.split('/')[-1]
        path_segments = [s for s in path.split('/') if s]
        
        if method == 'GET':
            if has_id_param:
                return 'detail'
            else:
                return 'list'
        elif method == 'POST':
            if has_id_param and len(path_segments) > 2:
                # POST /users/{id}/activate - action
                return 'action'
            else:
                return 'create'
        elif method in ['PUT', 'PATCH']:
            return 'update'
        elif method == 'DELETE':
            return 'delete'
        else:
            return 'action'
    
    def _detect_pagination_and_search(self, endpoint: Dict[str, Any], resource: Dict[str, Any]):
        """Detect if endpoint supports pagination and search"""
        params = endpoint.get('parameters', [])
        param_names = [p.get('name', '').lower() for p in params]
        
        # Pagination indicators
        pagination_params = ['page', 'limit', 'offset', 'size', 'per_page', 'pagesize']
        if any(p in param_names for p in pagination_params):
            resource['supports']['pagination'] = True
        
        # Search indicators
        search_params = ['q', 'query', 'search', 'filter', 'term']
        if any(p in param_names for p in search_params):
            resource['supports']['search'] = True
    
    def _analyze_schemas(self, schemas: Dict[str, Any]):
        """Analyze schemas to understand field types and relationships"""
        for schema_name, schema in schemas.items():
            if not isinstance(schema, dict):
                continue
                
            properties = schema.get('properties', {})
            
            # Find corresponding resource
            resource_name = schema_name.lower().rstrip('s')  # users -> user
            if resource_name not in self.resources:
                resource_name = schema_name.lower()
                
            if resource_name in self.resources:
                resource = self.resources[resource_name]
                
                # Extract field information
                for field_name, field_schema in properties.items():
                    resource['fields'].add(field_name)
                    
                    # Detect primary key
                    if field_name.lower() in ['id', '_id', 'uuid', f"{resource_name}_id"]:
                        resource['primaryKey'] = field_name
                    
                    # Detect media fields
                    if self._is_media_field(field_name, field_schema):
                        if resource_name not in [r['resource'] for r in self.media_endpoints]:
                            self.media_endpoints.append({
                                'resource': resource_name,
                                'field': field_name,
                                'type': self._get_media_type(field_name, field_schema)
                            })
    
    def _is_media_field(self, field_name: str, field_schema: Dict[str, Any]) -> bool:
        """Check if field represents media content"""
        media_indicators = [
            'url', 'file', 'video', 'audio', 'image', 'photo', 'thumbnail',
            'stream', 'media', 'attachment', 'document', 'avatar'
        ]
        
        field_lower = field_name.lower()
        format_type = field_schema.get('format', '')
        
        return (any(indicator in field_lower for indicator in media_indicators) or
                format_type in ['uri', 'binary'] or
                field_schema.get('type') == 'string' and 'url' in field_lower)
    
    def _get_media_type(self, field_name: str, field_schema: Dict[str, Any]) -> str:
        """Determine media type from field"""
        field_lower = field_name.lower()
        if any(t in field_lower for t in ['video', 'stream']):
            return 'video'
        elif any(t in field_lower for t in ['image', 'photo', 'thumbnail', 'avatar']):
            return 'image'
        elif 'audio' in field_lower:
            return 'audio'
        elif any(t in field_lower for t in ['file', 'document', 'attachment']):
            return 'file'
        else:
            return 'url'
    
    def _detect_special_endpoints(self, endpoints: List[Dict[str, Any]]):
        """Detect authentication, analytics, and other special endpoints"""
        for endpoint in endpoints:
            path = endpoint.get('path', '').lower()
            tags = [tag.lower() for tag in endpoint.get('tags', [])]
            summary = endpoint.get('summary', '').lower()
            
            # Authentication endpoints
            if (any(auth in path for auth in ['auth', 'login', 'register', 'logout', 'token']) or
                any(auth in tags for auth in ['auth', 'authentication', 'security']) or
                any(auth in summary for auth in ['login', 'authenticate', 'token'])):
                self.auth_endpoints.append(endpoint)
            
            # Analytics endpoints
            elif (any(analytics in path for analytics in ['analytics', 'stats', 'metrics', 'reports']) or
                  any(analytics in tags for analytics in ['analytics', 'statistics', 'metrics', 'reporting'])):
                self.analytics_endpoints.append(endpoint)
            
            # Search endpoints
            elif ('search' in path or 'search' in tags or 'search' in summary):
                self.search_endpoints.append(endpoint)
            
            # Action endpoints (non-CRUD operations)
            elif (endpoint.get('method', '').upper() == 'POST' and 
                  len(path.split('/')) > 3 and 
                  '{' in path):
                action_name = path.split('/')[-1]
                if action_name not in ['', '{id}']:
                    self.action_endpoints.append({
                        'endpoint': endpoint,
                        'action': action_name,
                        'resource': path.split('/')[1] if len(path.split('/')) > 1 else 'unknown'
                    })
    
    def _build_relationships(self, endpoints: List[Dict[str, Any]], schemas: Dict[str, Any]):
        """Build relationships between resources"""
        for schema_name, schema in schemas.items():
            if not isinstance(schema, dict):
                continue
                
            properties = schema.get('properties', {})
            
            for field_name, field_schema in properties.items():
                # Look for foreign key relationships
                if field_name.lower().endswith('_id') or field_name.lower().endswith('id'):
                    potential_resource = field_name.lower().replace('_id', '').replace('id', '')
                    if potential_resource in self.resources:
                        if schema_name not in self.relationships:
                            self.relationships[schema_name] = []
                        self.relationships[schema_name].append({
                            'field': field_name,
                            'target_resource': potential_resource,
                            'type': 'many_to_one'
                        })
    
    def _infer_workflows(self) -> List[Dict[str, Any]]:
        """Infer common user workflows from the API structure"""
        workflows = []
        
        # Authentication workflow
        if self.auth_endpoints:
            workflows.append({
                'name': 'Authentication',
                'description': 'User login and token management',
                'steps': [ep for ep in self.auth_endpoints],
                'priority': 1
            })
        
        # CRUD workflows for each resource
        for resource_name, resource in self.resources.items():
            if resource['supports']['create'] or resource['supports']['update']:
                workflows.append({
                    'name': f"Manage {resource['displayName']}",
                    'description': f"Create, view, and manage {resource['displayName']}",
                    'steps': [
                        resource.get('listEndpoint'),
                        resource.get('createEndpoint'),
                        resource.get('detailEndpoint'),
                        resource.get('updateEndpoint')
                    ],
                    'resource': resource_name,
                    'priority': 2
                })
        
        # Media workflows
        if self.media_endpoints:
            workflows.append({
                'name': 'Media Management',
                'description': 'Upload and manage media files',
                'steps': self.media_endpoints,
                'priority': 3
            })
        
        return workflows
    
    def _build_navigation_structure(self) -> Dict[str, Any]:
        """Build a logical navigation structure"""
        nav = {
            'primary': [],
            'secondary': [],
            'utility': []
        }
        
        # Primary navigation - main resources
        for resource_name, resource in self.resources.items():
            if resource['supports']['list'] or resource['supports']['create']:
                nav['primary'].append({
                    'name': resource['displayName'],
                    'path': f"/{resource_name}",
                    'resource': resource_name,
                    'hasCreate': resource['supports']['create'],
                    'hasSearch': resource['supports']['search']
                })
        
        # Secondary navigation - special features
        if self.analytics_endpoints:
            nav['secondary'].append({
                'name': 'Analytics',
                'path': '/analytics',
                'type': 'analytics'
            })
        
        if self.search_endpoints:
            nav['utility'].append({
                'name': 'Search',
                'path': '/search',
                'type': 'search'
            })
        
        # Authentication
        if self.auth_endpoints:
            nav['utility'].append({
                'name': 'Authentication',
                'path': '/auth',
                'type': 'auth'
            })
        
        return nav
    
    def _humanize_name(self, name: str) -> str:
        """Convert technical names to human-readable format"""
        # Remove common prefixes/suffixes
        name = re.sub(r'^(api_|v\d+_)', '', name)
        
        # Convert snake_case and kebab-case to Title Case
        name = re.sub(r'[_-]', ' ', name)
        
        # Convert camelCase to Title Case
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        
        return name.title()


def create_semantic_chunks(api_summary: Dict[str, Any], semantic_model: Dict[str, Any], max_resources_per_chunk: int = 3) -> List[Dict[str, Any]]:
    """Create semantically meaningful chunks based on workflows and relationships"""
    chunks = []
    
    # Chunk 1: Authentication + Core Resources
    auth_chunk = {
        'chunk_name': 'Authentication & Core',
        'type': 'foundation',
        'priority': 1,
        'endpoints': [],
        'resources': [],
        'workflows': [],
        'info': api_summary.get('info', {}),
        'servers': api_summary.get('servers', []),
        'securitySchemes': api_summary.get('securitySchemes', {}),
        'navigation': semantic_model.get('navigation_structure', {})
    }
    
    # Add auth endpoints
    if semantic_model.get('auth', {}).get('endpoints'):
        auth_chunk['endpoints'].extend(semantic_model['auth']['endpoints'])
        auth_chunk['workflows'].extend([w for w in semantic_model.get('workflows', []) if w.get('name') == 'Authentication'])
    
    # Add primary resources (limit to avoid chunk overload)
    primary_resources = sorted(
        semantic_model.get('resources', {}).items(),
        key=lambda x: (x[1]['supports']['list'], x[1]['supports']['create']),
        reverse=True
    )
    
    for i, (resource_name, resource) in enumerate(primary_resources[:max_resources_per_chunk]):
        auth_chunk['resources'].append(resource)
        # Add all endpoints for this resource
        for operation in resource['operations'].values():
            auth_chunk['endpoints'].append(operation['endpoint'])
    
    chunks.append(auth_chunk)
    
    # Chunk 2+: Remaining resources grouped by relationships
    remaining_resources = dict(primary_resources[max_resources_per_chunk:])
    
    while remaining_resources:
        chunk = {
            'chunk_name': f'Resources Group {len(chunks)}',
            'type': 'resources',
            'priority': len(chunks) + 1,
            'endpoints': [],
            'resources': [],
            'workflows': [],
            'relationships': []
        }
        
        # Take next batch of resources
        batch = dict(list(remaining_resources.items())[:max_resources_per_chunk])
        remaining_resources = dict(list(remaining_resources.items())[max_resources_per_chunk:])
        
        for resource_name, resource in batch.items():
            chunk['resources'].append(resource)
            for operation in resource['operations'].values():
                chunk['endpoints'].append(operation['endpoint'])
            
            # Add related workflows
            chunk['workflows'].extend([
                w for w in semantic_model.get('workflows', [])
                if w.get('resource') == resource_name
            ])
            
            # Add relationships
            if resource_name in semantic_model.get('relationships', {}):
                chunk['relationships'].extend(semantic_model['relationships'][resource_name])
        
        chunks.append(chunk)
    
    # Special chunks for analytics, media, etc.
    if semantic_model.get('analytics'):
        chunks.append({
            'chunk_name': 'Analytics & Reporting',
            'type': 'analytics',
            'priority': 99,
            'endpoints': semantic_model['analytics'],
            'workflows': [w for w in semantic_model.get('workflows', []) if 'analytic' in w.get('name', '').lower()]
        })
    
    if semantic_model.get('media', {}).get('endpoints'):
        chunks.append({
            'chunk_name': 'Media Management',
            'type': 'media',
            'priority': 98,
            'endpoints': semantic_model['media']['endpoints'],
            'workflows': [w for w in semantic_model.get('workflows', []) if 'media' in w.get('name', '').lower()]
        })
    
    return chunks
