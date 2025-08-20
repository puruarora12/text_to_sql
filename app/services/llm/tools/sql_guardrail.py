from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict

from app import logger
from app.services.llm.session import LLMSession
from flask import current_app

import json
import re


@tool_call
@observe
def sql_guardrail(sql: str, schema_text: str = "", context_text: str = "") -> Dict[str, str]:
	"""
	Use an LLM as a judge/guardrail to validate a proposed SQL query against the provided
	database schema and RAG context. Enforces read-only rules and checks identifiers.

	Args:
	  sql: The SQL statement to validate
	  schema_text: Compact database schema summary
	  context_text: Vector search table descriptions

	Returns:
	  {"accept": true|false, "feedback": "..."}
	"""
	llm = LLMSession(
		chat_model=current_app.config.get("CHAT_MODEL"),
		embedding_model=current_app.config.get("EMBEDDING_MODEL"),
	)

	messages = [
		{
			"role": "system",
			"content": (
				"You are a strict SQL validator. Evaluate if the proposed SQL is safe and valid for DuckDB, "
				"and consistent with the provided schema/context. Enforce: read-only (SELECT/WITH only), no DDL/DML, "
				"and identifiers should plausibly exist in the schema/context. Respond in strict JSON with keys: accept (boolean), feedback (string)."
			),
		},
		{
			"role": "user",
			"content": (
				f"Schema (truncated):\n{schema_text}\n\nContext:\n{context_text}\n\nSQL to validate:\n{sql}\n\n"
				"Validation criteria:\n"
				"- Must start with SELECT or WITH.\n"
				"- No INSERT/UPDATE/DELETE/ALTER/DROP/CREATE.\n"
				"- Table and column identifiers should appear consistent with schema/context.\n"
				"- Provide clear feedback if not acceptable."
			),
		},
	]

	response = llm.chat(messages=messages)
	content = response.choices[0].message.content or ""

	# Try to parse JSON from the model
	try:
		# Extract fenced json if provided
		m = re.search(r"```json\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
		if m:
			content_json = m.group(1)
		else:
			content_json = content
		parsed = json.loads(content_json)
		accept = bool(parsed.get("accept", False))
		feedback = str(parsed.get("feedback", ""))
		return {"accept": accept, "feedback": feedback}
	except Exception:
		# Fallback heuristic: accept if starts with select/with and no disallowed verbs
		sql_lc = (sql or "").lower().strip()
		read_only = sql_lc.startswith("select") or sql_lc.startswith("with")
		disallowed = any(k in sql_lc for k in [" insert ", " update ", " delete ", " alter ", " drop ", " create "])
		accept = bool(read_only and not disallowed)
		return {"accept": accept, "feedback": content.strip()[:500]}


