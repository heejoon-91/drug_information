
import os
import sys
import asyncio
from unittest.mock import MagicMock, patch

# 1. Mock Environment Variable BEFORE importing module with global side-effect
os.environ["OPENAI_API_KEY"] = "sk-dummy-key-for-test"

# 2. Add project path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 3. Patch OpenAI client to avoid actual network calls during import/init
with patch("openai.OpenAI") as MockClient:
    # 4. Now import the service
    from services.ai_service import AIService

    async def verify_fix():
        print("--- [Verification Start] ---")
        
        # Test Case 1: Exception Handling Logic (Fallback)
        print("\nTest 1: AIService Exception Fallback")
        # Force the mock client's create method to raise an exception
        MockClient.return_value.chat.completions.create.side_effect = Exception("API Error")
        
        result = await AIService.classify_intent("배가 아파요")
        print(f"Result: {result}")
        
        if "fda_search_keywords" in result:
            print("✅ SUCCESS: Fallback returns 'fda_search_keywords'")
        else:
            print("❌ FAILURE: Fallback missing 'fda_search_keywords'")
            
        # Test Case 2: Intent Classifier Logic (Simulated Success)
        print("\nTest 2: AIService Normal Response")
        # Reset side effect
        MockClient.return_value.chat.completions.create.side_effect = None
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"category": "SYMPTOM_RELIEF", "fda_search_keywords": ["stomach ache"]}'
        MockClient.return_value.chat.completions.create.return_value = mock_response
        
        result_success = await AIService.classify_intent("배가 아파요")
        print(f"Result: {result_success}")
        
        if "fda_search_keywords" in result_success:
             print("✅ SUCCESS: Normal response contains 'fda_search_keywords'")
        else:
             print("❌ FAILURE: Normal response missing key")

        print("\n--- [Verification End] ---")

    if __name__ == "__main__":
        asyncio.run(verify_fix())
