from typing import Dict, List
import json

from flask import current_app

from app.core.commands import ReadCommand
from app.errors import ValidationException
from app.services.llm.session import LLMSession
from app.services.llm.tools.text_to_sql import text_to_sql as generate_sql
from app.services.llm.tools.db_schema_vector_search import db_schema_vector_search as fetch_context_and_schema
from app.commands.threads.create_session import get_session_metadata
from app.services.datastore.duckdb_datastore import DuckDBDatastore
from app.utils.formatters import get_timestamp

from langfuse.decorators import observe


# Simple in-memory conversation store keyed by session_id
_CONVERSATION_STORE: Dict[str, List[Dict[str, str]]] = {}


class ConversationCommand(ReadCommand):
	def __init__(self, session_id: str, incoming_messages: List[Dict[str, str]]):
		self.session_id = session_id
		self.incoming_messages = incoming_messages or []
		self.llm_session: LLMSession | None = None

	def validate(self) -> None:
		if not self.session_id:
			raise ValidationException("session_id is required.")
		if not isinstance(self.incoming_messages, list):
			raise ValidationException("messages must be a list.")

	@observe()
	def execute(self) -> Dict[str, str]:
		self.validate()
		history = _CONVERSATION_STORE.get(self.session_id, [])

		# Normalize any non-string content to JSON strings to satisfy tokenization
		for msg in history:
			content = msg.get("content")
			if not isinstance(content, str):
				msg["content"] = json.dumps(content, default=str)

		# Append incoming messages to session history
		for msg in self.incoming_messages:
			role = msg.get("role")
			content = msg.get("content")
			if not role or not content:
				continue
			history.append({
				"role": role,
				"content": content,
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

		# Check if this is a human verification response
		latest_user_msg = self._latest_user_message(history)
		if latest_user_msg.lower().strip() in ["yes", "no"]:
			# Look for the previous human verification request
			prev_assistant = self._get_previous_assistant_message(history)
			if prev_assistant and isinstance(prev_assistant, dict) and prev_assistant.get("type") == "human_verification":
				if latest_user_msg.lower().strip() == "yes":
					# Execute the pending query
					sql_query = prev_assistant.get("sql", "")
					if sql_query:
						try:
							datastore = DuckDBDatastore(database="app/data/data.db")
							df = datastore.execute(sql_query)
							rows = df.to_dict(orient="records") if not df.empty else []
							assistant_payload = {
								"sql": sql_query,
								"decision": "executed_after_verification",
								"feedback": "Query executed after user confirmation.",
								"row_count": len(rows),
								"rows": rows,
							}
						except Exception as e:
							assistant_payload = {
								"sql": sql_query,
								"decision": "execution_failed",
								"feedback": f"Execution failed after confirmation: {str(e)}",
							}
				else:
					# User said no
					assistant_payload = {
						"sql": prev_assistant.get("sql", ""),
						"decision": "cancelled_by_user",
						"feedback": "Query execution cancelled by user.",
					}
				
				history.append({
					"role": "assistant",
					"content": json.dumps(assistant_payload, default=str),
					"timestamp": (get_timestamp(with_nanoseconds=True),),
				})
				_CONVERSATION_STORE[self.session_id] = history
				return assistant_payload

		# Check if this is a human clarification response (not just yes/no)
		prev_assistant = self._get_previous_assistant_message(history)
		if prev_assistant and isinstance(prev_assistant, dict) and prev_assistant.get("type") == "human_verification" and prev_assistant.get("requires_clarification"):
			# This is a clarification response, regenerate SQL with additional context
			original_query = prev_assistant.get("original_query", "")
			user_clarification = latest_user_msg
			
			# Combine original query with user clarification
			enhanced_query = f"{original_query}. Additional clarification: {user_clarification}"
			
			# Fetch context and schema
			ctx = fetch_context_and_schema(natural_language_query=enhanced_query, n_results=3)
			context_text = (ctx or {}).get("context_text", "")
			schema_text = (ctx or {}).get("schema_text", "")

			# Get user_type from session metadata
			session_metadata = get_session_metadata(self.session_id)
			user_type = session_metadata.get("user_type", "user")

			# Generate new SQL with enhanced query
			gen = generate_sql(
				natural_language_query=enhanced_query,
				context_text=context_text,
				schema_text=schema_text,
				user_type=user_type,
			)
			
			sql_query = (gen or {}).get("query", "").strip()
			decision = str((gen or {}).get("decision", ""))
			feedback = str((gen or {}).get("feedback", ""))
			rows = (gen or {}).get("rows")
			row_count = (gen or {}).get("row_count")

			# Check if this is still a human verification request
			if gen.get("type") == "human_verification":
				assistant_payload = gen
			else:
				assistant_payload = {"sql": sql_query, "decision": decision, "feedback": feedback}
				if rows is not None:
					assistant_payload.update({"row_count": row_count, "rows": rows})

			history.append({
				"role": "assistant",
				"content": json.dumps(assistant_payload, default=str),
				"timestamp": (get_timestamp(with_nanoseconds=True),),
			})
			_CONVERSATION_STORE[self.session_id] = history
			return assistant_payload

		# Generate SQL via tool (which judges and may execute)
		user_req = self._latest_user_message(history)
		ctx = fetch_context_and_schema(natural_language_query=user_req, n_results=5)
		context_text = (ctx or {}).get("context_text", "")
		schema_text = (ctx or {}).get("schema_text", "")

		# Get user_type from session metadata
		session_metadata = get_session_metadata(self.session_id)
		user_type = session_metadata.get("user_type", "user")  # default to user if not found

		gen = generate_sql(
			natural_language_query=user_req,
			context_text=context_text,
			schema_text=schema_text,
			user_type=user_type,
		)
		sql_query = (gen or {}).get("query", "").strip()
		decision = str((gen or {}).get("decision", ""))
		feedback = str((gen or {}).get("feedback", ""))
		rows = (gen or {}).get("rows")
		row_count = (gen or {}).get("row_count")

		# Check if this is a human verification request
		if gen.get("type") == "human_verification":
			assistant_payload = gen  # Return the human verification payload as-is
		else:
			assistant_payload = {"sql": sql_query, "decision": decision, "feedback": feedback}
			if rows is not None:
				assistant_payload.update({"row_count": row_count, "rows": rows})

		history.append({
			"role": "assistant",
			"content": json.dumps(assistant_payload, default=str),
			"timestamp": (get_timestamp(with_nanoseconds=True),),
		})
		_CONVERSATION_STORE[self.session_id] = history

		return assistant_payload

	def _latest_user_message(self, history: List[Dict[str, str]]) -> str:
		for msg in reversed(history):
			if msg.get("role") == "user" and msg.get("content"):
				return msg.get("content")
		return ""

	def _get_previous_assistant_message(self, history: List[Dict[str, str]]) -> Dict:
		"""Get the most recent assistant message from history."""
		for msg in reversed(history):
			if msg.get("role") == "assistant" and msg.get("content"):
				try:
					return json.loads(msg.get("content"))
				except:
					return {}
		return {}
