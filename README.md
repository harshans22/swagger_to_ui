# 🚀 Swagger to UI Generator

Transform your OpenAPI/Swagger specifications into beautiful, functional web applications with semantic understanding and contextual UI generation.

## ✨ Features

### 🧠 Semantic Analysis
- **Resource Detection**: Automatically identifies domain entities (users, posts, products, etc.)
- **Relationship Mapping**: Understands connections between resources
- **Workflow Intelligence**: Infers user journeys and business processes
- **Action Recognition**: Detects specialized operations (like, subscribe, publish)

### 🎨 UI Generation Modes

1. **Semantic App UI** (Recommended)
   - Creates domain-specific interfaces like YouTube, Twitter, or e-commerce platforms
   - Builds resource-oriented pages with intuitive navigation
   - Handles media, authentication, analytics automatically
   - Uses contextual chunking for better LLM understanding

2. **API Console**
   - Interactive testing interface similar to Postman
   - Organized by API tags and operations
   - Real-time request/response handling

3. **Deterministic Static**
   - No LLM required, basic but functional
   - Stable output for CI/CD pipelines

### 🏗️ Architecture

```
api_to_ui/
├── main.py                 # Entry point with mode selection
├── parser/                 # OpenAPI parsing
│   ├── swagger_parser.py   # Comprehensive spec parsing
│   └── url_loader.py       # Remote spec loading
├── core/                   # Core logic
│   ├── semantic.py         # Semantic analysis engine
│   ├── chunking.py         # Smart chunking strategies
│   ├── summary.py          # API summarization
│   ├── ui_generation.py    # LLM-powered UI generation
│   └── static_ui_builder.py # Deterministic UI builder
└── ui/                     # Generated output
```

## 🚀 Quick Start

### 1. Installation

```bash
cd api_to_ui
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and configure Azure OpenAI:

```env
AZURE_OPENAI_API_KEY=your_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4
AZURE_OPENAI_API_VERSION=2024-02-01
```

### 3. Run

```bash
python main.py
```

Then:
1. Enter your OpenAPI spec URL or file path
2. Choose generation mode
3. Provide domain context (for semantic mode)
4. Wait for generation and open the result!

## 📋 Examples

### YouTube-like Platform
```
Domain Context: "YouTube-like video platform with user channels, subscriptions, 
video uploads, comments, and analytics dashboard"
```

**Generated Features:**
- Video feed with thumbnail cards
- Channel pages with subscriber counts
- Upload interface with file handling
- Comment threads with real-time updates
- Analytics dashboard with view metrics

### E-commerce Platform
```
Domain Context: "E-commerce platform with products, shopping cart, 
user accounts, and order management"
```

**Generated Features:**
- Product catalog with search/filters
- Shopping cart functionality
- User account management
- Order tracking interface
- Admin product management

### Social Media Platform
```
Domain Context: "Social media platform with user posts, likes, 
followers, and messaging"
```

**Generated Features:**
- Timeline/feed interface
- User profiles with follower counts
- Post creation with media upload
- Like/comment interactions
- Messaging interface

## 🧠 Semantic Analysis

The semantic analyzer understands:

### Resource Patterns
- `/users` → User management interface
- `/posts/{id}/comments` → Nested comment system
- `/products/{id}/reviews` → Product review interface

### Operation Types
- `GET /users` → List view with pagination
- `GET /users/{id}` → Detail view/profile
- `POST /users` → Create user form
- `POST /users/{id}/follow` → Action button

### Field Intelligence
- `videoUrl`, `streamUrl` → Video player components
- `thumbnail`, `avatar` → Image displays
- `userId`, `authorId` → Relationship dropdowns
- `createdAt`, `publishedAt` → Date formatting

### Special Endpoints
- `/auth/login` → Authentication module
- `/search` → Global search interface  
- `/analytics` → Dashboard widgets
- `/upload` → File upload interface

## 🎯 Chunking Strategy

The system uses intelligent chunking to handle large APIs:

1. **Foundation Chunk**: Authentication + core resources
2. **Resource Chunks**: Related entities grouped by relationships
3. **Special Chunks**: Analytics, media, admin features

Each chunk maintains context awareness for seamless integration.

## 🔧 Customization

### Adding New Semantic Patterns

Edit `core/semantic.py` to add domain-specific detection:

```python
def _detect_special_endpoints(self, endpoints):
    for endpoint in endpoints:
        path = endpoint.get('path', '').lower()
        
        # Add your custom detection
        if 'webhook' in path:
            self.webhook_endpoints.append(endpoint)
```

### Custom UI Templates

Modify the prompts in `core/ui_generation.py` for different UI frameworks or styles.

## 📊 Supported Features

### ✅ Implemented
- [x] Semantic resource detection
- [x] Relationship mapping  
- [x] Authentication handling
- [x] Media/file upload support
- [x] Search interface generation
- [x] Analytics dashboard
- [x] Responsive design
- [x] Dark/light themes
- [x] Real-time API calls

### 🚧 Coming Soon
- [ ] WebSocket/SSE support
- [ ] Advanced form validation
- [ ] Multi-language support
- [ ] Plugin architecture
- [ ] React/Vue code generation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add your improvements
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- 📧 Create an issue for bug reports
- 💡 Submit feature requests via discussions
- 📖 Check the wiki for advanced usage

---

**Transform your APIs into beautiful applications with just a few clicks!** 🎉
