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
from app.schemas.tool_schemas import (
    TextToSQLInput, TextToSQLOutput, SQLExecutionResult, DecisionType, ValidationStrategy,
    dict_to_text_to_sql_input, text_to_sql_output_to_dict
)
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
def text_to_sql(natural_language_query: str, context_text: str = "", schema_text: str = "", user_type: str = "user", previous_chat: str = "") -> Dict[str, Any]:
    """
    Generate a SQL query from a natural language request using provided context and schema.
    Includes validation and refinement loop with confidence scoring.

    Args:
      natural_language_query: The user's natural language question.
      context_text: Concise RAG snippets describing tables.
      schema_text: Compact schema summary.
      user_type: "user" or "admin" - determines permission level.
      previous_chat: Previous conversation context for better SQL generation.

    Returns:
      {"query": sql_text, "decision": "...", "feedback": "..."} or human verification payload
    """
    # Convert input to structured format
    input_data = TextToSQLInput(
        natural_language_query=natural_language_query,
        context_text=context_text,
        schema_text=schema_text,
        user_type=user_type,
        previous_chat=previous_chat
    )
    
    if not input_data.natural_language_query:
        logger.info("text_to_sql: empty natural language query")
        return text_to_sql_output_to_dict(TextToSQLOutput(
            query="",
            decision=DecisionType.REJECT,
            feedback="Empty natural language query"
        ))

    # Step 1: Generate initial SQL
    initial_result = _generate_initial_sql(input_data.natural_language_query, input_data.context_text, input_data.schema_text, input_data.previous_chat)
    if not initial_result.get("sql_text"):
        return text_to_sql_output_to_dict(TextToSQLOutput(
            query="",
            decision=DecisionType.REJECT,
            feedback="Failed to generate SQL query"
        ))

    sql_text = initial_result["sql_text"]
    logger.info(f"text_to_sql: initial SQL generated: {sql_text}")

    # Check if the query is too vague and needs clarification
    if sql_text == "VAGUE_QUERY":
        logger.info("text_to_sql: query too vague, requesting clarification")
        clarification_response = human_query_clarification(
            user_query=input_data.natural_language_query,
            db_schema=input_data.schema_text,
            context_data=input_data.context_text,
            failed_sql="",
            validation_feedback="Query is too vague to generate accurate SQL. Please provide more specific details.",
            attempts=1
        )
        # Add a flag to indicate this is a clarification request, not an execution confirmation
        clarification_response["requires_clarification"] = True
        clarification_response["sql"] = ""  # No SQL to execute
        return clarification_response

    # Step 2: Smart validation orchestration
    logger.info("text_to_sql: starting smart validation orchestration")
    validation_start_time = time.time()
    
    # Use the validation orchestrator for intelligent validation routing
    orchestration_result = validation_orchestrator(
        user_query=input_data.natural_language_query,
        generated_sql=sql_text,
        db_schema=input_data.schema_text,
        context_data=input_data.context_text,
        user_type=input_data.user_type
    )
    
    validation_time = time.time() - validation_start_time
    
    # Record validation metrics
    try:
        record_validation_result_metric(
            query_type=_determine_query_type(input_data.natural_language_query),
            query_complexity=orchestration_result.get("query_complexity", "unknown"),
            validation_strategy=orchestration_result.get("validation_strategy", "sequential"),
            total_validation_time=validation_time,
            steps_completed=orchestration_result.get("performance_metrics", {}).get("steps_completed", 0),
            parallel_steps=orchestration_result.get("performance_metrics", {}).get("parallel_steps", 0),
            is_valid=orchestration_result.get("is_valid", False),
            errors=orchestration_result.get("errors", []),
            warnings=orchestration_result.get("warnings", []),
            recommendations=orchestration_result.get("recommendations", []),
            user_query=input_data.natural_language_query,
            generated_sql=sql_text,
            validation_results=orchestration_result.get("validation_results", {})
        )
    except Exception as e:
        logger.error(f"Failed to record validation metrics: {e}")
    
    # Check if validation passed
    if orchestration_result.get("is_valid", False):
        logger.info("text_to_sql: validation orchestration passed")
        return _process_validated_sql(sql_text, input_data, orchestration_result)
    
    # If validation failed, check if we should request clarification
    errors = orchestration_result.get("errors", [])
    if errors and any("vague" in error.lower() or "clarification" in error.lower() for error in errors):
        logger.info("text_to_sql: validation failed due to vague query, requesting clarification")
        return human_query_clarification(
            user_query=input_data.natural_language_query,
            db_schema=input_data.schema_text,
            context_data=input_data.context_text,
            failed_sql=sql_text,
            validation_feedback="; ".join(errors),
            attempts=1
        )
    
    # For other validation failures, return error response
    logger.warning(f"text_to_sql: validation failed: {errors}")
    return text_to_sql_output_to_dict(TextToSQLOutput(
        query=sql_text,
        decision=DecisionType.REJECT,
        feedback=f"Validation failed: {'; '.join(errors)}",
        validation_time=validation_time,
        validation_strategy=ValidationStrategy(orchestration_result.get("validation_strategy", "sequential"))
    ))


def _generate_initial_sql(natural_language_query: str, context_text: str, schema_text: str, previous_chat: str = "") -> Dict[str, str]:
    """
    Generate the initial SQL query using the LLM with internal feedback mechanism.
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
        "QUERY TYPE HANDLING:\n"
        "- SELECT queries: Use for reading/retrieving data\n"
        "- INSERT queries: Use for adding new records to existing tables\n"
        "- UPDATE queries: Use for modifying existing records\n"
        "- DELETE queries: Use for removing records\n"
        "- CREATE TABLE queries: Use when user explicitly requests to create a new table\n"
        "- CREATE VIEW queries: Use when user requests to create a view\n"
        "- CREATE INDEX queries: Use when user requests to create an index\n\n"
        "SECURITY GUIDELINES:\n"
        "- Only access tables and columns that exist in the provided schema\n"
        "- Avoid system tables (information_schema, sys.*, pg_catalog)\n"
        "- Do not generate privilege escalation commands (GRANT, REVOKE)\n"
        "- Do not perform file operations (COPY TO, INTO OUTFILE)\n"
        "- Do not execute dangerous functions (xp_cmdshell, exec, system)\n"
        "- Generate only single, focused SQL statements\n\n"
        "TECHNICAL REQUIREMENTS:\n"
        "- Use fully-qualified table names when schema is provided\n"
        "- Add LIMIT 100 for SELECT queries if no explicit limit is specified\n"
        "- Return only the SQL statement; no explanations or comments\n"
        "- Use proper SQL syntax and quoting\n"
        "- Ensure WHERE clauses are properly structured\n"
        "- For case-insensitive string comparisons, use ILIKE instead of = (e.g., WHERE Channel ILIKE 'private label')\n"
        "- For exact case-insensitive matches, use UPPER() or LOWER() functions (e.g., WHERE UPPER(Channel) = UPPER('private label'))\n"
        "- For CREATE TABLE statements, include appropriate data types and constraints\n\n"
        "VAGUE QUERY HANDLING:\n"
        "- Only mark as VAGUE_QUERY if the request truly lacks sufficient detail\n"
        "- If context provides clear table/column references, use them to generate appropriate SQL\n"
        "- If schema contains relevant tables/columns, attempt to create a meaningful query\n"
        "- Use context data to infer missing details (e.g., if user says 'customers' and context shows 'customer' table, use that)\n"
        "- For CREATE queries, if user provides table structure details, generate the CREATE statement\n"
        "- Only generate VAGUE_QUERY when absolutely no meaningful query can be constructed\n\n"
        "INTERNAL FEEDBACK:\n"
        "- If the first attempt results in VAGUE_QUERY, reconsider using available context and schema\n"
        "- Look for table name variations (e.g., 'customer' vs 'customers')\n"
        "- Use context data to infer table names and relationships\n"
        "- Make reasonable assumptions based on available schema information"
    )

    # First attempt
    user_message = (
        f"Schema (truncated):\n{schema_text}\n\n"
        f"Context snippets:\n{context_text}\n\n"
        f"Previous chat context:\n{previous_chat}\n\n"
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
    
    # If first attempt results in VAGUE_QUERY, try again with more aggressive context usage
    if sql_text == "VAGUE_QUERY":
        logger.info("text_to_sql: First attempt resulted in VAGUE_QUERY, trying with enhanced context usage")
        
        enhanced_system_message = system_message + "\n\nENHANCED CONTEXT USAGE:\n" + (
            "- Be more aggressive in using available context and schema information\n"
            "- Make reasonable assumptions about table names and relationships\n"
            "- If user mentions a concept (e.g., 'customers'), look for similar table names in schema\n"
            "- Use context data to infer missing details\n"
            "- Only return VAGUE_QUERY if absolutely no meaningful query can be constructed"
        )
        
        enhanced_user_message = (
            f"Schema (truncated):\n{schema_text}\n\n"
            f"Context snippets:\n{context_text}\n\n"
            f"Previous chat context:\n{previous_chat}\n\n"
            f"User request:\n{natural_language_query}\n\n"
            f"IMPORTANT: Use available context and schema more aggressively. "
            f"Look for table name variations and make reasonable assumptions. "
            f"Only return VAGUE_QUERY if absolutely no meaningful query can be constructed."
        )
        
        enhanced_response = llm.chat(
            messages=[
                {"role": "system", "content": enhanced_system_message},
                {"role": "user", "content": enhanced_user_message},
            ]
        )
        enhanced_content = enhanced_response.choices[0].message.content or ""
        sql_text = _extract_sql_from_text(enhanced_content)
        
        if sql_text != "VAGUE_QUERY":
            logger.info(f"text_to_sql: Enhanced attempt successful, generated: {sql_text}")
    
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
    elif any(word in user_lower for word in ["add", "insert", "new", "register"]):
        return "insert"
    elif any(word in user_lower for word in ["create"]):
        return "create"
    elif any(word in user_lower for word in ["delete", "remove", "drop", "eliminate"]):
        return "delete"
    else:
        return "unknown"


def _process_validated_sql(sql_text: str, input_data: TextToSQLInput, orchestration_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process validated SQL and execute if accepted.
    """
    # Check if validation passed
    if not orchestration_result.get("is_valid", False):
        errors = orchestration_result.get("errors", [])
        return text_to_sql_output_to_dict(TextToSQLOutput(
            query=sql_text,
            decision=DecisionType.REJECT,
            feedback=f"Validation failed: {'; '.join(errors)}",
            validation_time=orchestration_result.get("total_validation_time", 0),
            validation_strategy=ValidationStrategy(orchestration_result.get("validation_strategy", "sequential"))
        ))
    
    # Check guardrail decision from orchestration results
    guardrail_result = orchestration_result.get("validation_results", {}).get("guardrail", {}).get("result", {})
    decision = guardrail_result.get("decision", "reject")
    feedback = guardrail_result.get("feedback", "")
    
    if decision == "accept":
        try:
            # Execute the query
            rows = execute_sql_query(sql_text)
            return text_to_sql_output_to_dict(TextToSQLOutput(
                query=sql_text,
                decision=DecisionType.ACCEPT,
                feedback=feedback,
                row_count=len(rows),
                rows=rows,
                validation_time=orchestration_result.get("total_validation_time", 0),
                validation_strategy=ValidationStrategy(orchestration_result.get("validation_strategy", "sequential"))
            ))
        except Exception as e:
            return text_to_sql_output_to_dict(TextToSQLOutput(
                query=sql_text,
                decision=DecisionType.REJECT,
                feedback=f"Execution failed: {str(e)}",
                validation_time=orchestration_result.get("total_validation_time", 0),
                validation_strategy=ValidationStrategy(orchestration_result.get("validation_strategy", "sequential"))
            ))
    elif decision == "human_verification":
        # Return human verification request with the SQL query included
        return {
            "type": "human_verification",
            "sql": sql_text,
            "feedback": feedback,
            "requires_clarification": False,  # This is execution confirmation, not clarification
            "original_query": input_data.natural_language_query,
            "message": f"I've generated a SQL query for you. Would you like me to execute it?\n\nSQL Query:\n{sql_text}\n\n**Reasoning:** {feedback}\n\nPlease respond with \"yes\" to execute or \"no\" to cancel."
        }
    else:
        return text_to_sql_output_to_dict(TextToSQLOutput(
            query=sql_text,
            decision=DecisionType.REJECT,
            feedback=feedback,
            validation_time=orchestration_result.get("total_validation_time", 0),
            validation_strategy=ValidationStrategy(orchestration_result.get("validation_strategy", "sequential"))
        ))


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