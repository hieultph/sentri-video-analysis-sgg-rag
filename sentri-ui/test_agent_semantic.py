#!/usr/bin/env python3
"""
Test agent với semantic search tool mới
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.assistant import get_assistant_agent, add_agent_state

def test_agent_with_semantic_search():
    """Test agent với câu hỏi để kiểm tra semantic search tool"""
    
    print("=== TESTING AGENT WITH SEMANTIC SEARCH ===")
    
    # Initialize agent
    agent = get_assistant_agent(user_id=1)
    
    # Add session state
    add_agent_state(agent, user_id="1", camera_id="1")
    
    print(f"Agent tools available: {[tool.name for tool in agent.tools]}")
    
    # Test queries
    test_questions = [
        "Camera có thấy người nào không?",
        "Có xe ô tô nào qua không?", 
        "Hôm nay thấy gì?",
        "Có gì bất thường không?"
    ]
    
    for question in test_questions:
        print(f"\n🤔 Test Question: '{question}'")
        print("-" * 50)
        
        try:
            # Agent will automatically choose appropriate tool
            response = agent.run(question, stream=False)
            print(f"✅ Agent Response:")
            print(response.content)
            
            # Check what tools were used
            if hasattr(response, 'tool_calls') and response.tool_calls:
                tools_used = [call.function.name for call in response.tool_calls]
                print(f"🔧 Tools used: {tools_used}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*80)

if __name__ == "__main__":
    test_agent_with_semantic_search()