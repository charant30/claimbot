
import sys
import os
from pathlib import Path

# Add backend to path (c:\Users\charan4170\chatbot\claimbot\backend)
backend_path = Path(__file__).parent / "backend"
sys.path.append(str(backend_path))

from app.orchestration.graphs.supervisor import agent_status
from app.orchestration.state import create_initial_state
from app.core.logging import logger

# Mock state
state = create_initial_state(
    thread_id="test_thread",
    user_id="test_user"
)

state["current_input"] = "check status INC-915E787A"
# state["intent"] = "check_status" # Not needed for agent_status, it just looks at current_input/claim_number

print("Running agent_status with input:", state["current_input"])

try:
    result = agent_status(state)
    print("Result:", result.get("claim_details"))
    print("Next Step:", result.get("next_step"))
except Exception as e:
    print("CRASHED:", e)
    import traceback
    traceback.print_exc()
