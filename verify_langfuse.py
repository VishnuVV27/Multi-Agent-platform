#!/usr/bin/env python3
"""
Verify Langfuse connection and credentials.

Run this to test if Langfuse is properly configured.
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

from src.config import settings
from src.observability.langfuse_client import get_langfuse_client

def verify_langfuse():
    """Verify Langfuse configuration."""
    print("🔍 Verifying Langfuse Configuration...")
    print()

    # Check env vars
    print("1️⃣  Environment Variables:")
    print(f"   LANGFUSE_PUBLIC_KEY: {settings.LANGFUSE_PUBLIC_KEY[:20]}..." if settings.LANGFUSE_PUBLIC_KEY else "   ❌ MISSING")
    print(f"   LANGFUSE_SECRET_KEY: {settings.LANGFUSE_SECRET_KEY[:20]}..." if settings.LANGFUSE_SECRET_KEY else "   ❌ MISSING")
    print(f"   LANGFUSE_HOST: {settings.LANGFUSE_HOST}")
    print(f"   ENABLE_LANGFUSE_TRACING: {settings.ENABLE_LANGFUSE_TRACING}")
    print()

    # Try to initialize client
    print("2️⃣  Initializing Langfuse Client:")
    try:
        langfuse = get_langfuse_client()
        print(f"   ✅ Client initialized: {langfuse.enabled}")
        
        if langfuse.enabled:
            print(f"   ✅ Connected to: {settings.LANGFUSE_HOST}")
            print()
            
            # Test a trace
            print("3️⃣  Testing Trace Creation:")
            try:
                trace_id = langfuse.trace_llm_call(
                    workflow_id="test_workflow_001",
                    agent_id="test_agent",
                    model="claude-3.5-sonnet",
                    prompt="Test prompt",
                    output="Test output",
                    input_tokens=10,
                    output_tokens=5,
                    cost=0.001,
                    latency_ms=100,
                    prompt_version="1.0",
                    metadata={"test": "verification"}
                )
                
                if trace_id:
                    print(f"   ✅ Test trace created: {trace_id}")
                    print()
                    print("🎉 Langfuse is properly configured!")
                    print()
                    print("📊 View your traces at:")
                    print(f"   {settings.LANGFUSE_HOST}/dashboard")
                    print()
                    return True
                else:
                    print("   ❌ Failed to create trace")
                    return False
                    
            except Exception as e:
                print(f"   ❌ Error creating trace: {e}")
                return False
        else:
            print("   ❌ Langfuse disabled (missing credentials)")
            return False
            
    except Exception as e:
        print(f"   ❌ Failed to initialize: {e}")
        return False

if __name__ == "__main__":
    success = verify_langfuse()
    sys.exit(0 if success else 1)
