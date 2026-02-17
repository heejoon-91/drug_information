import asyncio
import logging
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

# Load .env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(env_path)
print(f"Loaded .env from {env_path}")

# Map custom LANGSMITH_API_KEY to LANGCHAIN_API_KEY
if os.getenv("LANGSMITH_API_KEY") and not os.getenv("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
    print("Mapped LANGSMITH_API_KEY to LANGCHAIN_API_KEY")

# Enable LangSmith Tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"

from graph_agent.builder import build_graph

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_graph():
    print("Starting test_graph...")
    logger.info("Initializing Graph...")
    graph = build_graph()
    
    test_queries = [
        "머리가 너무 아파요",
        "타이레놀 효능이 뭐야?",
        "약은 식후 언제 먹어야 하나요?",
        "이상한질문입니다123"
    ]
    
    for q in test_queries:
        logger.info(f"\n--- Testing Query: {q} ---")
        try:
            inputs = {"query": q}
            result = await graph.ainvoke(inputs)
            
            category = result.get("category")
            keyword = result.get("keyword")
            final_answer = result.get("final_answer", "")
            
            logger.info(f"Category: {category}")
            logger.info(f"Keyword: {keyword}")
            logger.info(f"Final Answer (Snippet): {final_answer[:100]}...")
            
            if category == "symptom_recommendation":
                logger.info(f"DUR Data Count: {len(result.get('dur_data', []))}")
            elif category == "product_request":
                logger.info(f"FDA Brand Name: {result.get('fda_data', {}).get('brand_name')}")
            
        except Exception as e:
            logger.error(f"Error processing query '{q}': {e}")

if __name__ == "__main__":
    # Windows asyncio policy fix if needed, but usually fine for simple script
    asyncio.run(test_graph())
