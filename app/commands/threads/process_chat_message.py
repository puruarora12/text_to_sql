from typing import Dict, List
from flask import current_app, g

from app import logger
from app.core.commands import ReadCommand
from app.errors import ValidationException
from app.services.llm.prompts.chat_prompt import chat_prompt
from app.services.llm.session import LLMSession
from app.services.llm.structured_outputs import text_to_sql
from app.services.llm.tools.text_to_sql import text_to_sql as text_to_sql_tool
from app.utils.formatters import get_timestamp

from langfuse.decorators import observe
from openai import BadRequestError
from vaul import Toolkit
from uuid import uuid4

import json


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
        self.toolkit.add_tools(*[text_to_sql_tool])

    def validate(self) -> None:
        """
        Validate the command.
        """
        if not self.chat_messages:
            raise ValidationException("Chat messages are required.")
        
        return True
    
    def execute(self) -> None:
        """
        Execute the command.
        """
        logger.info(
            f'Command {self.__class__.__name__} started with {len(self.chat_messages)} messages.'
        )
        
        # Log input messages for debugging
        for i, msg in enumerate(self.chat_messages):
            logger.debug(f"Input message {i}: role={msg.get('role')}, content_preview={msg.get('content', '')[:100]}...")

        self.validate()

        prepared_messages = self.prepare_chat_messages()
        tool_schemas = self.toolkit.tool_schemas()
        
        logger.info(f"Prepared {len(prepared_messages)} messages for LLM")
        logger.info(f"Available tools: {[tool.get('function', {}).get('name', 'unknown') for tool in tool_schemas]}")

        chat_kwargs = {
            "messages": prepared_messages,
            "tools": tool_schemas,
        }

        try:
            logger.info("Sending request to LLM...")
            response = self.llm_session.chat(**chat_kwargs)
            logger.info(f"LLM response received. Finish reason: {response.choices[0].finish_reason}")
        except BadRequestError as e:
            logger.error(f"BadRequestError from LLM: {e}")
            raise e
        except Exception as e:
            logger.error(f"Failed to fetch chat response: {e}")
            raise ValidationException("Error in fetching chat response.")

        tool_messages = []

        response_message_config = {
            "role": "assistant",
            "content": response.choices[0].message.content,
            "finish_reason": response.choices[0].finish_reason,
        }

        if response.choices[0].finish_reason == "tool_calls":
            tool_calls = response.choices[0].message.tool_calls
            logger.info(f"LLM requested {len(tool_calls)} tool calls")

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

            response_message = self.format_message(**response_message_config)

            for i, tool_call in enumerate(tool_calls):
                logger.info(f"Executing tool call {i+1}/{len(tool_calls)}: {tool_call.function.name}")
                logger.debug(f"Tool call arguments: {tool_call.function.arguments}")
                
                try:
                    tool_run = self.execute_tool_call(tool_call)
                    logger.info(f"Tool call {tool_call.function.name} completed successfully")
                    logger.debug(f"Tool result preview: {str(tool_run)[:200]}...")
                except Exception as e:
                    logger.error(f"Tool call {tool_call.function.name} failed: {e}")
                    raise
                
                tool_messages.append(
                    self.format_message(
                        role="tool",
                        tool_call_id=tool_call.id,
                        content=json.dumps(tool_run),
                    )
                )
        else:
            logger.info("LLM provided direct response (no tool calls)")
            response_message = self.format_message(**response_message_config)

        # Add the messages as the last elements of the list
        self.chat_messages.append(response_message)
        self.chat_messages.extend(tool_messages)

        logger.info(f"Command completed. Returning {len(self.chat_messages)} total messages")
        return self.chat_messages
    

    @observe()
    def prepare_chat_messages(self) -> list:
        trimmed_messages = self.llm_session.trim_message_history(
            messages=self.chat_messages,
        )

        system_prompt = chat_prompt()

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
