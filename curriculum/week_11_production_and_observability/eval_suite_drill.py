import json

# This is a simulated Week 6 Evaluation Suite script
# Run this to see the test fail (RED), and then pass (GREEN)

# --- The Test Suite ---
TEST_CASES = [
    {"id": "test_1", "query": "What is the standard probation period?", "expected": "90 days", "status": "PASS"},
    {"id": "test_2", "query": "Is remote work allowed on Fridays?", "expected": "Yes", "status": "PASS"},
    {"id": "test_3", "query": "Can I carry over more than 5 vacation days?", "expected": "No", "status": "PASS"},
    # We are adding our new Failure-to-Test case here:
    {"id": "test_4", "query": "I am a senior director resigning. How much notice period?", "expected": "60 days", "status": "UNKNOWN"}
]

def run_suite(prompt_version):
    print(f"\n--- Running Evaluation Suite (Prompt Version: {prompt_version}) ---")
    pass_count = 0
    total = len(TEST_CASES)
    
    for case in TEST_CASES:
        if case["id"] == "test_4":
            # Simulate the bug behavior based on the prompt version
            if prompt_version == "v1.2_pre_effective_date_patch":
                # The old prompt fails to ignore the superseded policy
                result = "30 days"
            else:
                # The new prompt correctly prioritizes the active policy
                result = "60 days"
                
            if result == case["expected"]:
                print(f"[\033[92mPASS\033[0m] {case['id']}: expected '{case['expected']}', got '{result}'")
                pass_count += 1
            else:
                print(f"[\033[91mFAIL\033[0m] {case['id']}: expected '{case['expected']}', got '{result}'")
        else:
            print(f"[\033[92mPASS\033[0m] {case['id']}")
            pass_count += 1
            
    if pass_count == total:
        print(f"\nSUITE RESULT: \033[92mGREEN\033[0m ({pass_count}/{total} passed)\n")
    else:
        print(f"\nSUITE RESULT: \033[91mRED\033[0m ({pass_count}/{total} passed)\n")

# --- Run the drill ---
if __name__ == "__main__":
    # 1. Run the suite BEFORE the fix (This is what caused the bad trace in production)
    run_suite("v1.2_pre_effective_date_patch")
    
    # 2. Run the suite AFTER we bump the prompt version to fix the bug
    run_suite("v1.3_strict_effective_dates")
