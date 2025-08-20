from typing import Dict, List
from flask import current_app, g

from app import logger
from app.core.commands import ReadCommand
from app.errors import ValidationException
from app.services.llm.prompts.chat_prompt import chat_prompt
from app.services.llm.session import LLMSession
from app.services.llm.structured_outputs import text_to_sql
from app.services.llm.tools.text_to_sql import text_to_sql as text_to_sql_tool
from app.services.llm.tools.db_schema_vector_search import db_schema_vector_search as db_schema_vector_search_tool
from app.services.llm.tools.sql_guardrail import sql_guardrail as sql_guardrail_tool
from app.services.datastore.duckdb_datastore import DuckDBDatastore
from app.utils.formatters import get_timestamp

from langfuse.decorators import observe
from openai import BadRequestError
from vaul import Toolkit
from uuid import uuid4

import json
import re


class ProcessChatMessageCommand(ReadCommand):
    """
    Process a chat message.
    """
    def __init__(self, chat_messages: List[Dict[str, str]]) -> None:
        self.chat_messages = chat_messages
        self.llm_session = LLMSession(
            chat_model=current_app.config.get("CHAT_MODEL"),
            embedding_model=current_app.config.get("EMBEDDING_MODEL"),
        )
        self.toolkit = Toolkit()
        self.toolkit.add_tools(*[db_schema_vector_search_tool, text_to_sql_tool, sql_guardrail_tool])

    def validate(self) -> None:
        """
        Validate the command.
        """
        if not self.chat_messages:
            raise ValidationException("Chat messages are required.")
        
        return True
    
    def execute(self) -> List[Dict[str, str]]:
        """
        Execute the command.
        """
        logger.info(
            f'Command {self.__class__.__name__} started with {self.chat_messages} messages.'
        )

        self.validate()

        # Prepare conversation and tool schemas
        conversation_messages = self.prepare_chat_messages()
        tools = self.toolkit.tool_schemas()

        max_tool_loops = 3
        loop_index = 0

        while True:
            try:
                response = self.llm_session.chat(messages=conversation_messages, tools=tools)
            except BadRequestError as e:
                raise e
            except Exception as e:
                logger.error(f"Failed to fetch chat response: {e}")
                raise ValidationException("Error in fetching chat response.")

            finish_reason = response.choices[0].finish_reason
            assistant_content = response.choices[0].message.content

            response_message_config = {
                "role": "assistant",
                "content": assistant_content,
                "finish_reason": finish_reason,
            }

            if finish_reason == "tool_calls":
                tool_calls = response.choices[0].message.tool_calls
                response_message_config["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in tool_calls
                ]

                # Append assistant (with tool calls)
                conversation_messages.append(self.format_message(**response_message_config))

                # Execute tools and append tool results
                for tool_call in tool_calls:
                    tool_run = self.execute_tool_call(tool_call)
                    conversation_messages.append(
                        self.format_message(
                            role="tool",
                            tool_call_id=tool_call.id,
                            content=json.dumps(tool_run),
                        )
                    )

                    # If text_to_sql produced a query, execute it and append results
                    try:
                        if (
                            tool_call.function.name == "text_to_sql"
                            and isinstance(tool_run, dict)
                            and tool_run.get("query")
                        ):
                            sql_query = str(tool_run.get("query")).strip()
                            # Only allow SELECT/CTE queries
                            sql_lc = sql_query.lower().lstrip("(").strip()
                            if sql_lc.startswith("select") or sql_lc.startswith("with"):
                                datastore = DuckDBDatastore(database="app/data/data.db")
                                df = datastore.execute(sql_query)
                                rows = df.to_dict(orient="records") if not df.empty else []
                                conversation_messages.append(
                                    self.format_message(
                                        role="assistant",
                                        content=json.dumps(
                                            {"sql": sql_query, "row_count": len(rows), "rows": rows},
                                            default=str,
                                        ),
                                    )
                                )
                            else:
                                conversation_messages.append(
                                    self.format_message(
                                        role="assistant",
                                        content=json.dumps(
                                            {"sql": sql_query, "error": "Only read-only SELECT/CTE queries are executed."}
                                        ),
                                    )
                                )
                    except Exception as e:
                        conversation_messages.append(
                            self.format_message(
                                role="assistant",
                                content=json.dumps(
                                    {"error": "Failed to execute generated SQL", "details": str(e)}
                                ),
                            ),
                        )

                loop_index += 1
                if loop_index >= max_tool_loops:
                    break
                # Continue to allow the model to see tool outputs and issue additional tool calls
                continue
            else:
                # No tool calls; append assistant content and finish
                conversation_messages.append(self.format_message(**response_message_config))
                break

        self.chat_messages = conversation_messages
        return self.chat_messages
    

    @observe()
    def prepare_chat_messages(self) -> list:
        trimmed_messages = self.llm_session.trim_message_history(
            messages=self.chat_messages,
        )

        # Build RAG context from the latest user message (if any)
        user_request = ""
        for msg in reversed(trimmed_messages):
            if msg.get("role") == "user" and msg.get("content"):
                user_request = msg.get("content")
                break

        # Best-effort vector context by calling the vector service here
        
        # logger.info(f"User request: {user_request} context_text: {context_text} schema_text: {schema_text}")
        system_prompt = chat_prompt( user_request=user_request)
        logger.info(f"System prompt: {system_prompt}")

        trimmed_messages = system_prompt + trimmed_messages

        return trimmed_messages

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
        return self.toolkit.run_tool(
            name=tool_call.function.name,
            arguments=json.loads(tool_call.function.arguments),
        )

    def _extract_sql_from_text(self, text: str) -> str:
        """Extract SQL from content; supports fenced blocks and plain text."""
        if not text:
            return ""
        # ```sql ... ```
        match = re.search(r"```sql\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        # Any code block
        match = re.search(r"```\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()
        return text.strip()
