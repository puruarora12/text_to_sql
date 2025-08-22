from typing import Dict, List
from flask import current_app, g

from app import logger
from app.core.commands import ReadCommand
from app.errors import ValidationException
from app.services.llm.tools.db_schema_vector_search import db_schema_vector_search as fetch_context_and_schema
from app.services.llm.tools.text_to_sql import text_to_sql as generate_sql
from app.services.llm.tools.sql_guardrail import sql_guardrail as judge_sql
from app.services.llm.tools.human_verification import human_verification as hv_tool
from app.utils.formatters import get_timestamp

from langfuse.decorators import observe
from uuid import uuid4

import json
import re


class ProcessChatMessageCommand(ReadCommand):
    """
    Process a chat message.
    """
    def __init__(self, chat_messages: List[Dict[str, str]]) -> None:
        self.chat_messages = chat_messages

    def validate(self) -> None:
        """
        Validate the command.
        """
        if not self.chat_messages:
            raise ValidationException("Chat messages are required.")
        
        return True
    
    def execute(self) -> List[Dict[str, str]]:
        """
        Execute the command using direct helper calls: fetch context/schema -> generate SQL -> judge -> respond.
        """
        logger.info(
            f'Command {self.__class__.__name__} started with {self.chat_messages} messages.'
        )

        self.validate()

        # Extract latest user request
        latest_user_request = ""
        for msg in reversed(self.chat_messages):
            if msg.get("role") == "user" and msg.get("content"):
                latest_user_request = msg.get("content")
                break

        if not latest_user_request:
            raise ValidationException("No user message provided.")

        # 1) Fetch context and schema via helper
        try:
            ctx = fetch_context_and_schema(natural_language_query=latest_user_request, n_results=5)
            context_text = (ctx or {}).get("context_text", "")
            schema_text = (ctx or {}).get("schema_text", "")
        except Exception as e:
            logger.error(f"Failed to fetch context/schema: {e}")
            context_text = ""
            schema_text = ""

        # 2) Generate SQL with the LLM; tool now also judges and may execute
        # Determine user type; default to 'user' if not provided in latest message metadata
        user_type = "user"
        # 2) Generate SQL with the LLM; pass user_type for permission control
        gen = generate_sql(
            natural_language_query=latest_user_request,
            context_text=context_text,
            schema_text=schema_text,
            user_type=user_type,
        )
        sql_query = (gen or {}).get("query", "").strip()

        if not sql_query:
            assistant_payload = {"error": "Failed to generate SQL from the request."}
            self.chat_messages.append(
                self.format_message(role="assistant", content=json.dumps(assistant_payload))
            )
            return self.chat_messages

        # 3) Use tool's enriched payload (may contain rows if accepted and executed)
        decision = str((gen or {}).get("decision", ""))
        feedback = str((gen or {}).get("feedback", ""))
        rows = (gen or {}).get("rows")
        row_count = (gen or {}).get("row_count")
        assistant_payload = {"sql": sql_query, "decision": decision, "feedback": feedback}
        if rows is not None:
            assistant_payload.update({"row_count": row_count, "rows": rows})
        self.chat_messages.append(
            self.format_message(role="assistant", content=json.dumps(assistant_payload))
        )
        return self.chat_messages
    

    @observe()
    def prepare_chat_messages(self) -> list:
        # No longer used to construct a system/tool prompt; simply return the existing messages.
        return self.chat_messages

    @observe()
    def format_message(self, role: str, content: str, **kwargs) -> dict:
        return {
            "id": str(uuid4()),
            "role": role,
            "content": content,
            "timestamp": (get_timestamp(with_nanoseconds=True),),
            **kwargs,
        }

    @observe()
    def execute_tool_call(self, tool_call: dict) -> dict:
        # Retained for compatibility; not used in the direct helper pipeline.
        return {}

    def _extract_sql_from_text(self, text: str) -> str:
        if not text:
            return ""
        match = re.search(r"```sql\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r"```\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text.strip()
