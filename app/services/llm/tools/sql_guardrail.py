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

	# Choose the appropriate prompt based on user type
	if user_type.lower() == "admin":
		system_prompt = (
			"You are a SQL security validator for DuckDB for ADMIN users. Your job is to allow all legitimate administrative tasks while only blocking explicitly malicious queries.\n"
			"Classify queries as: 'accept', 'human_verification', 'reject'.\n\n"
			"ADMIN USER RULES (Very permissive - allow all read/write operations):\n"
			"- ACCEPT: ALL read operations (SELECT, WITH, DESCRIBE, SHOW TABLES, information_schema queries)\n"
			"- ACCEPT: ALL write operations (INSERT, UPDATE, DELETE) for data management\n"
			"- ACCEPT: ALL DDL operations (CREATE, ALTER, DROP, TRUNCATE) for database management\n"
			"- ACCEPT: ALL multi-statement operations for administrative tasks\n"
			"- ACCEPT: ALL system table access for legitimate administrative purposes\n"
			"- ACCEPT: ALL privilege management operations (GRANT, REVOKE) for admin users\n"
			"- ACCEPT: ALL schema exploration and database management queries\n"
			"- ACCEPT: ALL data manipulation operations\n"
			"- HUMAN_VERIFICATION: Only for operations that could cause significant data loss (e.g., DROP DATABASE)\n"
			"- REJECT: ONLY queries that are explicitly malicious:\n"
			"  * SQL injection patterns (OR 1=1, OR TRUE, AND 1=1, UNION SELECT, --, /* */)\n"
			"  * File operations (COPY TO, INTO OUTFILE)\n"
			"  * Dangerous function execution (xp_cmdshell, exec, system)\n"
			"  * Attempts to bypass security controls\n"
			"  * Queries that could compromise system integrity\n\n"
			"BE VERY PERMISSIVE for admin users. Allow all legitimate database operations.\n"
			"Only block queries that are explicitly trying to inject something into the database.\n"
			"Respond strictly as JSON: {\"decision\": \"accept|human_verification|reject\", \"feedback\": \"detailed security analysis\"}."
		)
	else:
		system_prompt = (
			"You are a SQL security validator for DuckDB for REGULAR users. Your job is to PROTECT the database from potential threats while allowing legitimate queries.\n"
			"Classify queries as: 'accept', 'human_verification', 'reject'.\n\n"
			"REGULAR USER RULES (Strict security):\n"
			"- HUMAN_VERIFICATION: ALL DELETE and DROP operations MUST go through human verification\n"
			"- HUMAN_VERIFICATION: DDL operations (CREATE, ALTER, DROP, TRUNCATE) that may be legitimate but risky\n"
			"- HUMAN_VERIFICATION: Multi-statement operations that may be legitimate\n"
			"- HUMAN_VERIFICATION: Operations that could impact data integrity\n\n"
			"SECURITY GUIDELINES (Strict approach):\n"
			"- REJECT: ANY query that could bypass authentication, access system tables, perform privilege escalation, access sensitive data, or show suspicious patterns\n"
			"- REJECT: Queries with boolean-based injection patterns (OR 1=1, OR TRUE, AND 1=1)\n"
			"- REJECT: Queries with comment-based injection patterns (--, /* */)\n"
			"- REJECT: Queries with union-based injection patterns (UNION SELECT)\n"
					"- REJECT: Queries with suspicious stacked queries (e.g., SELECT; DROP TABLE; SELECT)\n"
		"- REJECT: Queries that mix different operation types inappropriately (e.g., SELECT; INSERT; DELETE)\n"
		"- REJECT: Queries that access system tables (information_schema, sys.*, pg_catalog)\n"
		"- REJECT: Queries that perform privilege escalation (GRANT, REVOKE)\n"
		"- REJECT: Queries that access sensitive tables (users, passwords, admin, system)\n"
		"- REJECT: Queries that perform file operations (COPY TO, INTO OUTFILE)\n"
		"- REJECT: Queries that execute dangerous functions (xp_cmdshell, exec, system)\n"
		"- REJECT: Queries that attempt to gather system information\n"
		"- REJECT: Queries that attempt to bypass WHERE clauses maliciously\n"
		"- REJECT: Queries that attempt to access multiple tables inappropriately\n"
		"- REJECT: Queries with suspicious WHERE clause patterns (multiple OR/AND conditions that could be injection)\n\n"
		"- ACCEPT: Single-statement read (SELECT/WITH) or single-statement write (INSERT/UPDATE) that:\n"
		"  * Aligns with the provided schema/context\n"
		"  * Has no obvious security impact\n"
		"  * Uses appropriate limits (LIMIT clause is good)\n"
		"  * Doesn't access sensitive or system tables\n"
		"  * Doesn't contain suspicious patterns\n"
		"  * Broad data access (SELECT * FROM table) is acceptable for legitimate tables\n\n"
		"- ACCEPT: Multi-statement INSERT operations that:\n"
		"  * Insert data into legitimate tables (not system tables)\n"
		"  * Use consistent table structure across statements\n"
		"  * Don't mix different operation types suspiciously\n"
		"  * Are clearly for data management purposes\n"
		"  * Don't contain injection patterns or malicious code\n\n"
			"BE STRICT. Protect against threats while allowing legitimate queries.\n"
			"Respond strictly as JSON: {\"decision\": \"accept|human_verification|reject\", \"feedback\": \"detailed security analysis\"}."
		)

	messages = [
		{
			"role": "system",
			"content": system_prompt,
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
		is_insert_update = any(sql_lc.startswith(k) for k in ["insert", "update"])
		is_delete = sql_lc.startswith("delete")
		contains_drop = "drop" in sql_lc
		contains_ddl = any(k in sql_lc for k in [" alter ", " drop ", " create ", " truncate ", " grant ", " revoke "])
		contains_semicolon = ";" in sql_lc
		# Simple heuristic: multiple semicolons => multi-statement
		multi_stmt = sql_lc.count(";") > 1
		
		# Admin users get more permissive treatment
		if user_type.lower() == "admin":
			# For admin users, allow most DDL and DELETE operations
			if is_select or is_insert_update or is_delete or contains_ddl:
				return {"accept": True, "decision": "accept", "feedback": "Admin user - allowed operation"}
			if multi_stmt:
				return {"accept": False, "decision": "human_verification", "feedback": "Admin user - multi-statement requires verification"}
			return {"accept": False, "decision": "reject", "feedback": "Admin user - potentially malicious operation"}
		else:
						# Regular users get strict treatment
			# CRITICAL: DELETE and DROP operations always require human verification
			if is_delete or contains_drop:
				return {"accept": False, "decision": "human_verification", "feedback": "DELETE/DROP operations require human verification"}
			
			# Check for legitimate multi-statement INSERT operations
			if multi_stmt and is_insert_update:
				# Check if it's a legitimate multi-statement INSERT (consistent table structure)
				statements = [stmt.strip() for stmt in sql_lc.split(';') if stmt.strip()]
				all_insert = all(stmt.startswith('insert') for stmt in statements)
				if all_insert:
					return {"accept": True, "decision": "accept", "feedback": "Legitimate multi-statement INSERT operation"}
				else:
					return {"accept": False, "decision": "human_verification", "feedback": "Multi-statement operation requires verification"}
			
			if (is_select or is_insert_update) and not contains_ddl and not multi_stmt:
				return {"accept": True, "decision": "accept", "feedback": content.strip()[:500]}
			if contains_ddl:
				return {"accept": False, "decision": "human_verification", "feedback": content.strip()[:500]}
			return {"accept": False, "decision": "reject", "feedback": content.strip()[:500]}


