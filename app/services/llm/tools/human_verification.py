from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict


@tool_call
@observe
def human_verification(user_request: str, sql: str, explanation: str) -> Dict[str, str]:
    """
    Tool: Presents the risky SQL to the user and asks for explicit approval.

    Returns a standardized payload the client can render for confirmation.
    """
    return {
        "type": "human_verification",
        "user_request": user_request or "",
        "sql": sql or "",
        "explanation": explanation or "",
        "prompt": "This operation may affect your data or security. Reply with 'yes' to run, or 'no' to cancel.",
    }

