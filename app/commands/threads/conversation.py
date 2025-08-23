from typing import Dict, List, Any
import json

from flask import current_app
from app import logger

from app.core.commands import ReadCommand
from app.errors import ValidationException
from app.services.llm.session import LLMSession
from app.services.llm.tools.text_to_sql import text_to_sql
from app.services.llm.tools.sql_execution_handler import sql_execution_handler
from app.services.llm.tools.db_schema_vector_search import db_schema_vector_search as fetch_context_and_schema
from app.commands.threads.create_session import get_session_metadata
from app.services.datastore.duckdb_datastore import DuckDBDatastore
from app.utils.formatters import get_timestamp
from app.schemas.tool_schemas import (
    ConversationCommandInput, ConversationCommandOutput, ConversationMessage,
    DecisionType, TextToSQLInput, DBSchemaVectorSearchInput
)

from langfuse.decorators import observe


# Simple in-memory conversation store keyed by session_id
_CONVERSATION_STORE: Dict[str, List[Dict[str, str]]] = {}


class ConversationCommand(ReadCommand):
	def __init__(self, session_id: str, incoming_messages: List[Dict[str, str]]):
		self.session_id = session_id
		self.incoming_messages = incoming_messages or []
		self.llm_session: LLMSession | None = None
		
		# Convert to structured input
		self.input_data = ConversationCommandInput(
			session_id=session_id,
			incoming_messages=[
				ConversationMessage(
					role=msg.get("role", ""),
					content=msg.get("content", ""),
					timestamp=msg.get("timestamp")
				) for msg in incoming_messages or []
			]
		)

	def validate(self) -> None:
		if not self.input_data.session_id:
			raise ValidationException("session_id is required.")
		if not isinstance(self.input_data.incoming_messages, list):
			raise ValidationException("messages must be a list.")

	@observe()
	def execute(self) -> Dict[str, str]:
		self.validate()
		history = _CONVERSATION_STORE.get(self.input_data.session_id, [])

		# Normalize any non-string content to JSON strings to satisfy tokenization
		for msg in history:
			content = msg.get("content")
			if not isinstance(content, str):
				msg["content"] = json.dumps(content, default=str)

		# Append incoming messages to session history
		for msg in self.input_data.incoming_messages:
			if not msg.role or not msg.content:
				continue
			history.append({
				"role": msg.role,
				"content": msg.content,
				"timestamp": (get_timestamp(with_nanoseconds=True),),
			})

		# Initialize LLM session inside app context
		if self.llm_session is None:
			self.llm_session = LLMSession(
				chat_model=current_app.config.get("CHAT_MODEL"),
				embedding_model=current_app.config.get("EMBEDDING_MODEL"),
			)

		# Trim history to fit model limits
		messages = self.llm_session.trim_message_history(history)

		# Check if this is a human verification response (yes/no for execution confirmation)
		latest_user_msg = self._latest_user_message(history)
		prev_assistant = self._get_previous_assistant_message(history)
		
		# Debug logging
		logger.info(f"conversation: latest_user_msg: '{latest_user_msg}'")
		logger.info(f"conversation: prev_assistant type: {type(prev_assistant)}")
		logger.info(f"conversation: history length: {len(history)}")
		logger.info(f"conversation: full history:")
		for i, msg in enumerate(history):
			logger.info(f"conversation:   {i}: role={msg.get('role')}, content={msg.get('content', '')[:100]}...")
		logger.info(f"conversation: last few messages:")
		for i, msg in enumerate(history[-3:]):
			logger.info(f"conversation:   {i}: role={msg.get('role')}, content={msg.get('content', '')[:100]}...")
		
		if isinstance(prev_assistant, dict):
			logger.info(f"conversation: prev_assistant keys: {list(prev_assistant.keys())}")
			logger.info(f"conversation: prev_assistant type: {prev_assistant.get('type')}")
			logger.info(f"conversation: prev_assistant requires_clarification: {prev_assistant.get('requires_clarification')}")
			logger.info(f"conversation: prev_assistant has_sql: {bool(prev_assistant.get('sql'))}")
		
		# Check if previous message was a human verification request
		if prev_assistant and isinstance(prev_assistant, dict) and prev_assistant.get("type") == "human_verification":
			logger.info(f"conversation: Found human verification request, checking user response")
			
			# Check if current user message is a yes/no response
			if latest_user_msg.lower().strip() in ["yes", "no", "y", "n", "execute", "run", "ok", "sure", "proceed", "cancel", "stop", "abort", "don't", "dont"]:
				logger.info(f"conversation: User response '{latest_user_msg}' detected as yes/no response")
				
				# Check if this is a clarification request (requires_clarification=True and no SQL) or execution confirmation
				if prev_assistant.get("requires_clarification") and (not prev_assistant.get("sql") or prev_assistant.get("sql") == ""):
					logger.info(f"conversation: This is a clarification request, user should provide more details")
					# This is a clarification request - user should provide more details, not yes/no
					assistant_payload = {
						"type": "clarification_needed",
						"message": "Please provide more specific details about your request instead of yes/no. I need more information to understand what you're looking for.",
						"original_query": prev_assistant.get("original_query", ""),
						"clarification_questions": prev_assistant.get("clarification_questions", []),
						"suggested_tables": prev_assistant.get("suggested_tables", [])
					}
				elif prev_assistant.get("sql") and prev_assistant.get("sql") != "":
					logger.info(f"conversation: This is an execution confirmation, using SQL execution handler")
					# This is an execution confirmation - use the SQL execution handler
					sql_query = prev_assistant.get("sql", "")
					original_feedback = prev_assistant.get("feedback", "")
					
					try:
						# Use the dedicated SQL execution handler
						execution_result = sql_execution_handler(
							sql_query=sql_query,
							user_response=latest_user_msg,
							original_feedback=original_feedback
						)
						
						# Process the execution result
						assistant_payload = self._process_sql_execution_response(execution_result)
						
					except Exception as e:
						logger.error(f"conversation: Error in SQL execution handler: {e}")
						# Handle any exceptions from sql_execution_handler
						assistant_payload = {
							"type": "error",
							"message": f"Error processing execution confirmation: {str(e)}",
							"sql": sql_query,
							"decision": "error",
							"feedback": f"Exception occurred: {str(e)}"
						}
				else:
					logger.warning(f"conversation: No SQL query found in human verification request")
					# No SQL query to execute
					assistant_payload = {
						"type": "error",
						"message": "No SQL query found to execute. Please try rephrasing your request.",
						"original_query": prev_assistant.get("original_query", "")
					}
				
				history.append({
					"role": "assistant",
					"content": json.dumps(assistant_payload, default=str),
					"timestamp": (get_timestamp(with_nanoseconds=True),),
				})
				_CONVERSATION_STORE[self.input_data.session_id] = history
				return assistant_payload
			else:
				logger.info(f"conversation: User response '{latest_user_msg}' is not a yes/no response, treating as clarification")

		# Check if this is a human clarification response (not just yes/no)
		prev_assistant = self._get_previous_assistant_message(history)
		if prev_assistant and isinstance(prev_assistant, dict) and prev_assistant.get("type") == "human_verification" and prev_assistant.get("requires_clarification") and (not prev_assistant.get("sql") or prev_assistant.get("sql") == ""):
			# This is a clarification response, regenerate SQL with additional context
			original_query = prev_assistant.get("original_query", "")
			user_clarification = latest_user_msg
			
			# Combine original query with user clarification
			enhanced_query = f"{original_query}. Additional clarification: {user_clarification}"
			
			# Extract previous chat context for this clarification
			previous_chat = self._extract_previous_chat_context(history)
			
			# Fetch context and schema
			ctx = fetch_context_and_schema(natural_language_query=enhanced_query, n_results=3)
			context_text = (ctx or {}).get("context_text", "")
			schema_text = (ctx or {}).get("schema_text", "")

			# Get user_type from session metadata
			session_metadata = get_session_metadata(self.input_data.session_id)
			user_type = session_metadata.get("user_type", "user")

			# Generate new SQL with enhanced query
			try:
				gen = text_to_sql(
					natural_language_query=enhanced_query,
					context_text=context_text,
					schema_text=schema_text,
					user_type=user_type,
					previous_chat=previous_chat,
				)
			except Exception as e:
				# Handle any exceptions from text_to_sql
				gen = {
					"type": "error",
					"message": f"Error generating SQL with clarification: {str(e)}",
					"sql": "",
					"decision": "error",
					"feedback": f"Exception occurred: {str(e)}"
				}
			
			# Safely extract fields with proper fallbacks
			sql_query = (gen or {}).get("query", "").strip() if isinstance(gen, dict) else ""
			decision = str((gen or {}).get("decision", "")) if isinstance(gen, dict) else ""
			feedback = str((gen or {}).get("feedback", "")) if isinstance(gen, dict) else ""
			rows = (gen or {}).get("rows") if isinstance(gen, dict) else None
			row_count = (gen or {}).get("row_count") if isinstance(gen, dict) else None

			# Determine what to return based on the response type
			assistant_payload = self._process_text_to_sql_response(gen, sql_query, decision, feedback, rows, row_count)

			history.append({
				"role": "assistant",
				"content": json.dumps(assistant_payload, default=str),
				"timestamp": (get_timestamp(with_nanoseconds=True),),
			})
			_CONVERSATION_STORE[self.input_data.session_id] = history
			return assistant_payload

		# Generate SQL via tool (which judges and may execute)
		user_req = self._latest_user_message(history)
		previous_chat = self._extract_previous_chat_context(history)
		ctx = fetch_context_and_schema(natural_language_query=user_req, n_results=5)
		context_text = (ctx or {}).get("context_text", "")
		schema_text = (ctx or {}).get("schema_text", "")

		# Get user_type from session metadata
		session_metadata = get_session_metadata(self.input_data.session_id)
		user_type = session_metadata.get("user_type", "user")  # default to user if not found

		# Check if this is a regeneration request
		regeneration_feedback = ""
		failed_sql = ""
		prev_assistant = self._get_previous_assistant_message(history)
		if prev_assistant and prev_assistant.get("type") == "regeneration_request":
			regeneration_feedback = prev_assistant.get("feedback", "")
			failed_sql = prev_assistant.get("sql", "")
			logger.info(f"conversation: Detected regeneration request with feedback: {regeneration_feedback}")
			logger.info(f"conversation: Failed SQL was: {failed_sql}")

		try:
			gen = text_to_sql(
				natural_language_query=user_req,
				context_text=context_text,
				schema_text=schema_text,
				user_type=user_type,
				previous_chat=previous_chat,
				regeneration_feedback=regeneration_feedback,
				failed_sql=failed_sql,
			)
		except Exception as e:
			# Handle any exceptions from text_to_sql
			gen = {
				"type": "error",
				"message": f"Error generating SQL: {str(e)}",
				"sql": "",
				"decision": "error",
				"feedback": f"Exception occurred: {str(e)}"
			}
		
		# Safely extract fields with proper fallbacks
		sql_query = (gen or {}).get("query", "").strip() if isinstance(gen, dict) else ""
		decision = str((gen or {}).get("decision", "")) if isinstance(gen, dict) else ""
		feedback = str((gen or {}).get("feedback", "")) if isinstance(gen, dict) else ""
		rows = (gen or {}).get("rows") if isinstance(gen, dict) else None
		row_count = (gen or {}).get("row_count") if isinstance(gen, dict) else None

		# Determine what to return based on the response type
		assistant_payload = self._process_text_to_sql_response(gen, sql_query, decision, feedback, rows, row_count)

		history.append({
			"role": "assistant",
			"content": json.dumps(assistant_payload, default=str),
			"timestamp": (get_timestamp(with_nanoseconds=True),),
		})
		_CONVERSATION_STORE[self.input_data.session_id] = history

		return assistant_payload

	def _latest_user_message(self, history: List[Dict[str, str]]) -> str:
		for msg in reversed(history):
			if msg.get("role") == "user" and msg.get("content"):
				return msg.get("content")
		return ""

	def _get_previous_assistant_message(self, history: List[Dict[str, str]]) -> Dict:
		"""Get the most recent assistant message from history."""
		logger.info(f"conversation: Looking for previous assistant message in history of length {len(history)}")
		
		for i, msg in enumerate(reversed(history)):
			logger.info(f"conversation: Checking message {len(history) - i - 1}: role={msg.get('role')}, has_content={bool(msg.get('content'))}")
			
			if msg.get("role") == "assistant" and msg.get("content"):
				try:
					content = msg.get("content")
					logger.info(f"conversation: Found assistant message, parsing content: {content[:100]}...")
					parsed = json.loads(content)
					logger.info(f"conversation: Successfully parsed assistant message: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}")
					return parsed
				except Exception as e:
					logger.error(f"conversation: Failed to parse assistant message: {e}")
					logger.error(f"conversation: Raw content: {msg.get('content')}")
					return {}
		
		logger.warning(f"conversation: No assistant message found in history")
		return {}

	def _extract_previous_chat_context(self, history: List[Dict[str, str]]) -> str:
		"""Extract previous chat context for better SQL generation."""
		if len(history) <= 1:  # Only current message or no history
			return ""
		
		# Get the last 5 messages (excluding the current one) for context
		context_messages = history[-6:-1]  # Exclude the current message
		context_parts = []
		
		for msg in context_messages:
			role = msg.get("role", "")
			content = msg.get("content", "")
			
			if role == "user":
				context_parts.append(f"User: {content}")
			elif role == "assistant":
				# Try to extract meaningful content from assistant messages
				try:
					parsed_content = json.loads(content)
					if isinstance(parsed_content, dict):
						# Extract SQL query if present
						if parsed_content.get("sql"):
							context_parts.append(f"Assistant SQL: {parsed_content['sql']}")
						# Extract feedback if present
						elif parsed_content.get("feedback"):
							context_parts.append(f"Assistant: {parsed_content['feedback']}")
						# Extract message if present
						elif parsed_content.get("message"):
							context_parts.append(f"Assistant: {parsed_content['message']}")
						else:
							context_parts.append(f"Assistant: {str(parsed_content)}")
					else:
						context_parts.append(f"Assistant: {str(parsed_content)}")
				except:
					# If parsing fails, use raw content
					context_parts.append(f"Assistant: {content}")
		
		return "\n".join(context_parts)

	def _process_text_to_sql_response(self, gen: Dict[str, Any], sql_query: str, decision: str, feedback: str, rows: Any, row_count: Any) -> Dict[str, Any]:
		"""
		Process the response from text_to_sql tool and return appropriate output.
		Handles all possible response types:
		- Human verification requests (clarification and execution confirmation)
		- Successful query execution
		- Query rejections and errors
		- Empty or invalid responses
		"""
		# Handle empty or invalid responses
		if not gen or not isinstance(gen, dict):
			return {
				"type": "error",
				"message": "Failed to generate a valid response. Please try again.",
				"sql": "",
				"decision": "error",
				"feedback": "Invalid response from text-to-SQL tool"
			}

		# Handle human verification requests
		if gen.get("type") == "human_verification":
			# Ensure all required fields are present
			verification_response = {
				"type": "human_verification",
				"sql": gen.get("sql", ""),
				"feedback": gen.get("feedback", ""),
				"requires_clarification": gen.get("requires_clarification", False),
				"original_query": gen.get("original_query", ""),
				"message": gen.get("message", "")
			}
			
			# Add optional fields if present
			if "clarification_questions" in gen:
				verification_response["clarification_questions"] = gen["clarification_questions"]
			if "suggested_tables" in gen:
				verification_response["suggested_tables"] = gen["suggested_tables"]
			if "query_type" in gen:
				verification_response["query_type"] = gen["query_type"]
			if "action_word" in gen:
				verification_response["action_word"] = gen["action_word"]
			if "clarity_score" in gen:
				verification_response["clarity_score"] = gen["clarity_score"]
			if "vague_aspects" in gen:
				verification_response["vague_aspects"] = gen["vague_aspects"]
			
			return verification_response

		# Handle successful query execution
		if decision == "accept" and rows is not None:
			# Return complete response with all fields for proper frontend display
			response = {
				"sql": sql_query,
				"decision": decision,
				"feedback": feedback,
				"rows": rows,
				"row_count": row_count
			}
			
			# Add additional fields if available
			if "validation_time" in gen:
				response["validation_time"] = gen["validation_time"]
			if "validation_strategy" in gen:
				response["validation_strategy"] = gen["validation_strategy"]
			if "query_complexity" in gen:
				response["query_complexity"] = gen["query_complexity"]
			if "performance_metrics" in gen:
				response["performance_metrics"] = gen["performance_metrics"]
			
			return response

		# Handle query rejections and errors
		if decision in ["reject", "error", "execution_failed"]:
			response = {
				"sql": sql_query,
				"decision": decision,
				"feedback": feedback
			}
			
			# Add additional fields if available
			if "validation_time" in gen:
				response["validation_time"] = gen["validation_time"]
			if "validation_strategy" in gen:
				response["validation_strategy"] = gen["validation_strategy"]
			if "query_complexity" in gen:
				response["query_complexity"] = gen["query_complexity"]
			if "performance_metrics" in gen:
				response["performance_metrics"] = gen["performance_metrics"]
			
			# Add rows if present (for partial results)
			if rows is not None:
				response["rows"] = rows
				response["row_count"] = row_count
			
			return response

		# Handle regeneration requests
		if gen.get("type") == "regeneration_request":
			response = {
				"type": "regeneration_request",
				"sql": gen.get("sql", ""),
				"feedback": gen.get("feedback", ""),
				"requires_clarification": gen.get("requires_clarification", False),
				"original_query": gen.get("original_query", ""),
				"user_friendly_message": gen.get("user_friendly_message", ""),
				"technical_details": gen.get("technical_details", ""),
				"suggested_fixes": gen.get("suggested_fixes", []),
				"message": gen.get("message", ""),
				"decision": "regeneration_request"
			}
			return response

		# Handle other decision types (human_verification, executed_after_verification, etc.)
		if decision in ["human_verification", "executed_after_verification", "cancelled_by_user"]:
			response = {
				"sql": sql_query,
				"decision": decision,
				"feedback": feedback
			}
			
			# Add rows if present
			if rows is not None:
				response["rows"] = rows
				response["row_count"] = row_count
			
			return response

		# Handle unknown decision types
		return {
			"type": "unknown_response",
			"sql": sql_query,
			"decision": decision,
			"feedback": feedback,
			"message": f"Received unknown decision type: {decision}",
			"original_response": gen
		}

	def _process_sql_execution_response(self, execution_result: Dict[str, Any]) -> Dict[str, Any]:
		"""
		Process the response from sql_execution_handler tool and return appropriate output.
		Handles execution confirmations, cancellations, and ambiguous responses.
		"""
		# Handle empty or invalid responses
		if not execution_result or not isinstance(execution_result, dict):
			return {
				"type": "error",
				"message": "Failed to process execution response. Please try again.",
				"sql": "",
				"decision": "error",
				"feedback": "Invalid response from SQL execution handler"
			}

		# Handle regeneration requests first (they have a different structure)
		if execution_result.get("type") == "regeneration_request":
			response = {
				"type": "regeneration_request",
				"sql": execution_result.get("sql", ""),
				"feedback": execution_result.get("feedback", ""),
				"requires_clarification": execution_result.get("requires_clarification", False),
				"original_query": execution_result.get("original_query", ""),
				"user_friendly_message": execution_result.get("user_friendly_message", ""),
				"technical_details": execution_result.get("technical_details", ""),
				"suggested_fixes": execution_result.get("suggested_fixes", []),
				"message": execution_result.get("message", ""),
				"decision": "regeneration_request",
				"user_response": execution_result.get("user_response", "")
			}
			return response

		# Safely extract fields with proper fallbacks
		sql_query = (execution_result or {}).get("query", "").strip() if isinstance(execution_result, dict) else ""
		decision = str((execution_result or {}).get("decision", "")) if isinstance(execution_result, dict) else ""
		feedback = str((execution_result or {}).get("feedback", "")) if isinstance(execution_result, dict) else ""
		rows = (execution_result or {}).get("rows") if isinstance(execution_result, dict) else None
		row_count = (execution_result or {}).get("row_count") if isinstance(execution_result, dict) else None
		user_response = (execution_result or {}).get("user_response", "") if isinstance(execution_result, dict) else ""

		# Handle successful execution after verification
		if decision == "executed_after_verification" and rows is not None:
			# Return complete response with all fields for proper frontend display
			response = {
				"sql": sql_query,
				"decision": decision,
				"feedback": feedback,
				"rows": rows,
				"row_count": row_count,
				"user_response": user_response
			}
			return response

		# Handle user cancellation
		if decision == "cancelled_by_user":
			response = {
				"sql": sql_query,
				"decision": decision,
				"feedback": feedback,
				"user_response": user_response
			}
			return response

		# Handle execution failures
		if decision in ["reject", "error", "execution_failed"]:
			response = {
				"sql": sql_query,
				"decision": decision,
				"feedback": feedback,
				"user_response": user_response
			}
			
			# Add rows if present (for partial results)
			if rows is not None:
				response["rows"] = rows
				response["row_count"] = row_count
			
			return response

		# Handle ambiguous responses (ask for clarification)
		if decision == "human_verification":
			response = {
				"type": "human_verification",
				"sql": sql_query,
				"feedback": feedback,
				"requires_clarification": False,  # This is execution confirmation, not clarification
				"original_query": "",
				"message": feedback,
				"user_response": user_response
			}
			return response

		# Handle unknown decision types
		return {
			"type": "unknown_response",
			"sql": sql_query,
			"decision": decision,
			"feedback": feedback,
			"message": f"Received unknown decision type: {decision}",
			"user_response": user_response,
			"original_response": execution_result
		}
