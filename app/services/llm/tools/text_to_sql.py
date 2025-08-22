from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict, Any, List
import re
import time

from app import logger
from app.services.llm.session import LLMSession
from app.services.llm.tools.sql_query_validator import human_query_clarification
from app.services.llm.tools.validation_orchestrator import validation_orchestrator
from app.services.llm.tools.validation_metrics import record_validation_result_metric
from app.services.datastore.duckdb_datastore import DuckDBDatastore
from flask import current_app


def execute_sql_query(sql_text: str) -> List[Dict[str, Any]]:
    """
    Execute SQL query and return results as list of dictionaries.
    """
    try:
        datastore = DuckDBDatastore(database="app/data/data.db")
        df = datastore.execute(sql_text)
        return df.to_dict(orient="records") if not df.empty else []
    except Exception as e:
        logger.error(f"Error executing SQL query: {e}")
        raise e


@tool_call
@observe
def text_to_sql(natural_language_query: str, context_text: str = "", schema_text: str = "", user_type: str = "user") -> Dict[str, Any]:
    """
    Generate a SQL query from a natural language request using provided context and schema.
    Includes validation and refinement loop with confidence scoring.

    Args:
      natural_language_query: The user's natural language question.
      context_text: Concise RAG snippets describing tables.
      schema_text: Compact schema summary.
      user_type: "user" or "admin" - determines permission level.

    Returns:
      {"query": sql_text, "decision": "...", "feedback": "..."} or human verification payload
    """
    if not natural_language_query:
        logger.info("text_to_sql: empty natural language query")
        return {}

    # Step 1: Generate initial SQL
    initial_result = _generate_initial_sql(natural_language_query, context_text, schema_text)
    if not initial_result.get("sql_text"):
        return {"query": "", "decision": "reject", "feedback": "Failed to generate SQL query"}

    sql_text = initial_result["sql_text"]
    logger.info(f"text_to_sql: initial SQL generated: {sql_text}")

    # Check if the query is too vague and needs clarification
    if sql_text == "VAGUE_QUERY":
        logger.info("text_to_sql: query too vague, requesting clarification")
        return human_query_clarification(
            user_query=natural_language_query,
            db_schema=schema_text,
            context_data=context_text,
            failed_sql="",
            validation_feedback="Query is too vague to generate accurate SQL. Please provide more specific details.",
            attempts=1
        )

    # Step 2: Smart validation orchestration
    logger.info("text_to_sql: starting smart validation orchestration")
    validation_start_time = time.time()
    
    # Use the validation orchestrator for intelligent validation routing
    orchestration_result = validation_orchestrator(
                user_query=natural_language_query,
        generated_sql=sql_text,
                db_schema=schema_text,
                context_data=context_text,
        user_type=user_type
    )
    
    validation_time = time.time() - validation_start_time
    
    # Record validation metrics
    try:
        record_validation_result_metric(
            query_type=_determine_query_type(natural_language_query),
            query_complexity=orchestration_result.get("query_complexity", "unknown"),
            validation_strategy=orchestration_result.get("validation_strategy", "sequential"),
            total_validation_time=validation_time,
            steps_completed=orchestration_result.get("performance_metrics", {}).get("steps_completed", 0),
            parallel_steps=orchestration_result.get("performance_metrics", {}).get("parallel_steps", 0),
            is_valid=orchestration_result.get("is_valid", False),
            errors=orchestration_result.get("errors", []),
            warnings=orchestration_result.get("warnings", []),
            recommendations=orchestration_result.get("recommendations", []),
            user_query=natural_language_query,
            generated_sql=sql_text,
            validation_results=orchestration_result.get("validation_results", {})
        )
    except Exception as e:
        logger.error(f"Failed to record validation metrics: {e}")
    
    # Check if validation passed
    if orchestration_result.get("is_valid", False):
        logger.info("text_to_sql: validation orchestration passed")
        return _process_validated_sql(sql_text, natural_language_query, context_text, schema_text, user_type, orchestration_result)
    
    # If validation failed, check if we should request clarification
    errors = orchestration_result.get("errors", [])
    if errors and any("vague" in error.lower() or "clarification" in error.lower() for error in errors):
        logger.info("text_to_sql: validation failed due to vague query, requesting clarification")
        return human_query_clarification(
            user_query=natural_language_query,
            db_schema=schema_text,
            context_data=context_text,
            failed_sql=sql_text,
            validation_feedback="; ".join(errors),
            attempts=1
        )
    
    # For other validation failures, return error response
    logger.warning(f"text_to_sql: validation failed: {errors}")
    return {
        "query": sql_text,
        "decision": "reject",
        "feedback": f"Validation failed: {'; '.join(errors)}",
        "validation_time": validation_time,
        "validation_strategy": orchestration_result.get("validation_strategy", "sequential")
    }


def _generate_initial_sql(natural_language_query: str, context_text: str, schema_text: str) -> Dict[str, str]:
    """
    Generate the initial SQL query using the LLM.
    """
    llm = LLMSession(
        chat_model=current_app.config.get("CHAT_MODEL"),
        embedding_model=current_app.config.get("EMBEDDING_MODEL"),
    )

    system_message = (
        "You are an expert DuckDB SQL generator. Using ONLY the provided schema and context data, "
        "produce a single, executable SQL statement that accurately answers the user's request.\n\n"
        "SCHEMA AND CONTEXT USAGE:\n"
        "- ALWAYS reference the provided database schema to ensure table and column names are correct\n"
        "- Use context data to understand the user's intent and make informed decisions about table selection\n"
        "- If context mentions specific tables, columns, or relationships, incorporate them in your query\n"
        "- When context provides examples or patterns, follow similar query structures\n"
        "- If schema shows table relationships, use appropriate JOINs based on foreign keys\n\n"
        "SECURITY GUIDELINES:\n"
        "- Only access tables and columns that exist in the provided schema\n"
        "- Avoid system tables (information_schema, sys.*, pg_catalog)\n"
        "- Do not generate privilege escalation commands (GRANT, REVOKE)\n"
        "- Do not perform file operations (COPY TO, INTO OUTFILE)\n"
        "- Do not execute dangerous functions (xp_cmdshell, exec, system)\n"
        "- Generate only single, focused SQL statements\n\n"
        "TECHNICAL REQUIREMENTS:\n"
        "- Use fully-qualified table names when schema is provided\n"
        "- Add LIMIT 100 if no explicit limit is specified\n"
        "- Return only the SQL statement; no explanations or comments\n"
        "- Use proper SQL syntax and quoting\n"
        "- Ensure WHERE clauses are properly structured\n\n"
        "VAGUE QUERY HANDLING:\n"
        "- If the user request lacks sufficient detail to create a meaningful query (e.g., 'show me data', 'get customers'), "
        "include 'VAGUE_QUERY' in your response\n"
        "- If context data doesn't provide enough information to determine the user's intent, mark as VAGUE_QUERY\n"
        "- If schema doesn't contain tables/columns that match the user's request, mark as VAGUE_QUERY\n"
        "- Only generate VAGUE_QUERY when the request truly cannot be interpreted with available schema and context\n"
        "- When context provides clear table/column references, use them to generate appropriate SQL"
    )

    user_message = (
        f"Schema (truncated):\n{schema_text}\n\n"
        f"Context snippets:\n{context_text}\n\n"
        f"User request:\n{natural_language_query}"
    )

    response = llm.chat(
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]
    )
    content = response.choices[0].message.content or ""
    sql_text = _extract_sql_from_text(content)
    
    return {"sql_text": sql_text}


def _determine_query_type(user_query: str) -> str:
    """
    Determine the type of query based on user input.
    """
    user_lower = user_query.lower()
    
    if any(word in user_lower for word in ["show", "get", "find", "select", "display", "list", "retrieve", "see", "view"]):
        return "read"
    elif any(word in user_lower for word in ["update", "change", "modify", "set", "edit", "alter"]):
        return "update"
    elif any(word in user_lower for word in ["add", "insert", "create", "new", "register"]):
        return "insert"
    elif any(word in user_lower for word in ["delete", "remove", "drop", "eliminate"]):
        return "delete"
    else:
        return "unknown"


def _process_validated_sql(sql_text: str, natural_language_query: str, context_text: str, schema_text: str, user_type: str, orchestration_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process validated SQL and execute if accepted.
    """
    # Check if validation passed
    if not orchestration_result.get("is_valid", False):
        errors = orchestration_result.get("errors", [])
        return {
            "query": sql_text,
            "decision": "reject",
            "feedback": f"Validation failed: {'; '.join(errors)}",
            "validation_time": orchestration_result.get("total_validation_time", 0),
            "validation_strategy": orchestration_result.get("validation_strategy", "sequential")
        }
    
    # Check guardrail decision from orchestration results
    guardrail_result = orchestration_result.get("validation_results", {}).get("guardrail", {}).get("result", {})
    decision = guardrail_result.get("decision", "reject")
    feedback = guardrail_result.get("feedback", "")
    
    if decision == "accept":
        try:
            # Execute the query
            rows = execute_sql_query(sql_text)
            return {
                "query": sql_text,
                "decision": "accept",
                "feedback": feedback,
                "row_count": len(rows), 
                "rows": rows,
                "validation_time": orchestration_result.get("total_validation_time", 0),
                "validation_strategy": orchestration_result.get("validation_strategy", "sequential")
            }
        except Exception as e:
            return {
                "query": sql_text,
                "decision": "reject",
                "feedback": f"Execution failed: {str(e)}",
                "validation_time": orchestration_result.get("total_validation_time", 0),
                "validation_strategy": orchestration_result.get("validation_strategy", "sequential")
            }
    elif decision == "human_verification":
        try:
            # Execute the query
            rows = execute_sql_query(sql_text)
            return {
                "query": sql_text,
                "decision": "executed_after_verification",
                "feedback": feedback,
                "row_count": len(rows), 
                "rows": rows,
                "validation_time": orchestration_result.get("total_validation_time", 0),
                "validation_strategy": orchestration_result.get("validation_strategy", "sequential")
            }
        except Exception as e:
            return {
                "query": sql_text,
                "decision": "reject",
                "feedback": f"Execution failed: {str(e)}",
                "validation_time": orchestration_result.get("total_validation_time", 0),
                "validation_strategy": orchestration_result.get("validation_strategy", "sequential")
            }
    else:
        return {
            "query": sql_text,
            "decision": "reject",
            "feedback": feedback,
            "validation_time": orchestration_result.get("total_validation_time", 0),
            "validation_strategy": orchestration_result.get("validation_strategy", "sequential")
        }


def _extract_sql_from_text(text: str) -> str:
    """Extract SQL from model output, handling optional code fences and vague query detection."""
    if not text:
        return ""
    
    # Check if this is a vague query response
    if "VAGUE_QUERY" in text.upper():
        return "VAGUE_QUERY"
    
    # Prefer ```sql blocks
    match = re.search(r"```sql\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Any code block
    match = re.search(r"```\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text.strip()