from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict
import re

from app import logger
from app.services.llm.session import LLMSession
from flask import current_app
import json


@tool_call
@observe
def sql_guardrail(sql: str, user_type: str = "user") -> Dict[str, str]:
	"""
	Use an LLM as a judge/guardrail to validate a proposed SQL query.
	This guardrail classifies the query into one of:
	- accept: safe to run (pure read or pure write and consistent with context)
	- human_verification: potentially risky (DDL, multi-statement, security-impacting) but may be intended
	- reject: irrelevant or clearly dangerous

	Returns both a boolean 'accept' for backward compatibility and a 'decision' string.
	"""

	llm = LLMSession(
		chat_model=current_app.config.get("CHAT_MODEL"),
		embedding_model=current_app.config.get("EMBEDDING_MODEL"),
	)

	messages = [
		{
			"role": "system",
			"content": (
				"You are a SQL security validator for DuckDB. Your job is to PROTECT the database from potential threats while allowing legitimate queries.\n"
				"Classify queries as: 'accept', 'human_verification', 'reject'.\n\n"
				"SECURITY GUIDELINES (BALANCED APPROACH):\n"
				"- REJECT: ANY query that could bypass authentication, access system tables, perform privilege escalation, access sensitive data, or show suspicious patterns\n"
				"- REJECT: Queries with boolean-based injection patterns (OR 1=1, OR TRUE, AND 1=1)\n"
				"- REJECT: Queries with comment-based injection patterns (--, /* */)\n"
				"- REJECT: Queries with union-based injection patterns (UNION SELECT)\n"
				"- REJECT: Queries with stacked queries or multiple statements\n"
				"- REJECT: Queries that access system tables (information_schema, sys.*, pg_catalog)\n"
				"- REJECT: Queries that perform privilege escalation (GRANT, REVOKE)\n"
				"- REJECT: Queries that access sensitive tables (users, passwords, admin, system)\n"
				"- REJECT: Queries that perform file operations (COPY TO, INTO OUTFILE)\n"
				"- REJECT: Queries that execute dangerous functions (xp_cmdshell, exec, system)\n"
				"- REJECT: Queries that attempt to gather system information\n"
				"- REJECT: Queries that attempt to bypass WHERE clauses maliciously\n"
				"- REJECT: Queries that attempt to access multiple tables inappropriately\n"
				"- REJECT: Queries with suspicious WHERE clause patterns (multiple OR/AND conditions that could be injection)\n\n"
				"- HUMAN_VERIFICATION: DDL operations (CREATE, ALTER, DROP, TRUNCATE) that may be legitimate but risky\n"
				"- HUMAN_VERIFICATION: Multi-statement operations that may be legitimate\n"
				"- HUMAN_VERIFICATION: Operations that could impact data integrity\n\n"
				"- ACCEPT: Single-statement read (SELECT/WITH) or single-statement write (INSERT/UPDATE/DELETE) that:\n"
				"  * Aligns with the provided schema/context\n"
				"  * Has no obvious security impact\n"
				"  * Uses appropriate limits (LIMIT clause is good)\n"
				"  * Doesn't access sensitive or system tables\n"
				"  * Doesn't contain suspicious patterns\n"
				"  * Broad data access (SELECT * FROM table) is acceptable for legitimate tables\n\n"
				"BE BALANCED. Allow legitimate queries while protecting against real threats.\n"
				"Respond strictly as JSON: {\"decision\": \"accept|human_verification|reject\", \"feedback\": \"detailed security analysis\"}."
			),
		},
		{
			"role": "user",
			"content": (
				f"SQL to validate:\n{sql}\n\n"
				"Analyze this SQL for ANY potential security threats or suspicious patterns. Be very aggressive in detection."
			),
		},
	]

	response = llm.chat(messages=messages)
	content = response.choices[0].message.content or ""

	try:
		m = re.search(r"```json\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
		content_json = m.group(1) if m else content
		parsed = json.loads(content_json)
		decision = str(parsed.get("decision", "reject")).strip().lower()
		feedback = str(parsed.get("feedback", ""))
		accept = decision == "accept"
		return {"accept": accept, "decision": decision, "feedback": feedback}
	except Exception:
		sql_lc = (sql or "").lower().strip()
		is_select = sql_lc.startswith("select") or sql_lc.startswith("with")
		is_single_write = any(sql_lc.startswith(k) for k in ["insert", "update", "delete"])
		contains_ddl = any(k in sql_lc for k in [" alter ", " drop ", " create ", " truncate ", " grant ", " revoke "])
		contains_semicolon = ";" in sql_lc
		# Simple heuristic: multiple semicolons => multi-statement
		multi_stmt = sql_lc.count(";") > 1
		if (is_select or is_single_write) and not contains_ddl and not multi_stmt:
			return {"accept": True, "decision": "accept", "feedback": content.strip()[:500]}
		if contains_ddl or multi_stmt:
			return {"accept": False, "decision": "human_verification", "feedback": content.strip()[:500]}
		return {"accept": False, "decision": "reject", "feedback": content.strip()[:500]}


