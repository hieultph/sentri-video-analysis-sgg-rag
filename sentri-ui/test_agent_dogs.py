"""
Test agent with improved instructions
"""
import sys
sys.path.insert(0, '.')

def test_agent_with_dogs():
    """Test agent with clear dog-related queries"""
    print("🤖 Testing agent with improved instructions...")
    
    try:
        from agents.assistant import get_assistant_agent
        
        # Create agent
        agent = get_assistant_agent(user_id=1)
        print("✓ Agent created")
        
        # Test queries that should work now
        test_queries = [
            "Có con chó nào xuất hiện không?",
            "Camera đã thấy chó chưa?",
            "Show me any dogs detected",
            "Tìm kiếm các scene có dog"
        ]
        
        for query in test_queries:
            print(f"\n" + "="*50)
            print(f"User: {query}")
            print("-"*50)
            
            try:
                # Run agent
                response = agent.run(query)
                print(f"Agent: {response.content}")
                
                # Check if response indicates dogs were found
                if any(word in response.content.lower() for word in ["có", "phát hiện", "scene", "dog", "chó"]):
                    if not any(negative in response.content.lower() for negative in ["chưa", "không", "không có"]):
                        print("✅ SUCCESS: Agent found dogs!")
                    else:
                        print("❌ ISSUE: Agent says no dogs found")
                else:
                    print("❓ Unclear response")
                    
            except Exception as e:
                print(f"❌ Agent error: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_agent_with_dogs()