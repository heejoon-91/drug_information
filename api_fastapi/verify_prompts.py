import sys
import os

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(current_dir)

from prompts.system_prompts import INTENT_CLASS_PROMPT
from prompts.answer_prompts import SYMPTOM_RESPONSE_PROMPT

def test_prompts():
    print("="*50)
    print(" [TESTING] INTENT_CLASS_PROMPT")
    print("="*50)
    print(INTENT_CLASS_PROMPT.format(user_query="두통이 있어"))
    
    print("\n" + "="*50)
    print(" [TESTING] SYMPTOM_RESPONSE_PROMPT")
    print("="*50)
    print(SYMPTOM_RESPONSE_PROMPT.format(symptom="두통", data="[Ibuprofen: NSAID, avoid if pregnant]"))

if __name__ == "__main__":
    test_prompts()
