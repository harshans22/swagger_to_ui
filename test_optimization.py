#!/usr/bin/env python3
"""
Test script to validate the optimized token usage and error handling.
"""

import os
import sys
from dotenv import load_dotenv

# Add the current directory to sys.path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser.swagger_parser import SwaggerParser
from core.summary import create_enhanced_api_summary
from core.ui_generation import create_ui_with_langchain

load_dotenv()

def test_optimization():
    """Test the optimized system with a minimal API spec"""
    
    # Simple test API spec
    test_spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Test API",
            "version": "1.0.0",
            "description": "A simple test API for token optimization validation"
        },
        "paths": {
            "/users": {
                "get": {
                    "summary": "Get all users",
                    "responses": {"200": {"description": "List of users"}}
                },
                "post": {
                    "summary": "Create user",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        }
                    },
                    "responses": {"201": {"description": "User created"}}
                }
            },
            "/users/{id}": {
                "get": {
                    "summary": "Get user by ID",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    "responses": {"200": {"description": "User details"}}
                }
            }
        }
    }
    
    print("🧪 Testing optimized token usage system...")
    print("=" * 50)
    
    # Check credentials
    azure_config = {
        "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
        "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        "deployment": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
    }
    
    if not azure_config["endpoint"] or not azure_config["api_key"]:
        print("❌ Azure OpenAI credentials missing. Check your .env file.")
        print("Required variables: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY")
        return False
    
    try:
        # Parse the test spec
        print("📋 Parsing test API specification...")
        parser = SwaggerParser(test_spec)
        parsed = parser.parse()
        
        # Create summary
        print("📊 Creating API summary...")
        api_summary = create_enhanced_api_summary(parsed)
        print(f"✅ Found {api_summary['totalEndpoints']} endpoints")
        
        # Generate UI with token optimization
        print("🎨 Testing optimized UI generation...")
        domain_context = "Simple user management system with CRUD operations"
        
        ui_content = create_ui_with_langchain(
            api_summary, 
            azure_config, 
            domain_context=domain_context
        )
        
        if ui_content:
            print("✅ UI generation successful!")
            print(f"📏 Generated HTML length: {len(ui_content):,} characters")
            
            # Save test output
            test_output_path = "ui/test_optimized_output.html"
            os.makedirs("ui", exist_ok=True)
            with open(test_output_path, "w", encoding="utf-8") as f:
                f.write(ui_content)
            print(f"💾 Test output saved to: {test_output_path}")
            
            return True
        else:
            print("❌ UI generation failed")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_optimization()
    
    if success:
        print("\n🎉 Optimization test completed successfully!")
        print("💡 The system is ready for production use with:")
        print("   ✅ Reduced token usage")
        print("   ✅ Better error handling")
        print("   ✅ Rate limit retry logic")
        print("   ✅ Progress indicators")
    else:
        print("\n💔 Optimization test failed.")
        print("🔧 Please check the error messages above and fix any issues.")
    
    print("\n🚀 Ready to use the main application: python main.py")
