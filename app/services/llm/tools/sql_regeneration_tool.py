from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict, Any, List
import re
import time

from app import logger
from app.services.llm.session import LLMSession
from app.services.llm.tools.validation_orchestrator import validation_orchestrator
from app.services.llm.tools.sql_execution_analyzer import sql_execution_analyzer
from app.services.datastore.duckdb_datastore import DuckDBDatastore
from app.schemas.tool_schemas import (
    SQLRegenerationInput, SQLRegenerationOutput, DecisionType, ValidationStrategy,
    dict_to_sql_regeneration_input, sql_regeneration_output_to_dict
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
def sql_regeneration_tool(
    original_query: str,
    failed_sql: str,
    failure_reason: str,
    context_text: str = "",
    schema_text: str = "",
    user_type: str = "user",
    previous_chat: str = "",
    failure_type: str = "validation"  # "validation" or "execution"
) -> Dict[str, Any]:
    """
    Regenerate SQL query when the original fails validation or execution.
    
    Args:
        original_query: The original natural language query from the user
        failed_sql: The SQL query that failed
        failure_reason: The reason for failure (validation error or execution error)
        context_text: Context data for better SQL generation
        schema_text: Database schema information
        user_type: "user" or "admin" - determines permission level
        previous_chat: Previous conversation context
        failure_type: "validation" or "execution" - type of failure
        
    Returns:
        Regenerated SQL query with validation and execution results
    """
    # Convert input to structured format
    input_data = SQLRegenerationInput(
        original_query=original_query,
        failed_sql=failed_sql,
        failure_reason=failure_reason,
        context_text=context_text,
        schema_text=schema_text,
        user_type=user_type,
        previous_chat=previous_chat,
        failure_type=failure_type
    )
    
    if not input_data.original_query:
        logger.info("sql_regeneration_tool: empty original query")
        return sql_regeneration_output_to_dict(SQLRegenerationOutput(
            original_query="",
            failed_sql=failed_sql,
            regenerated_sql="",
            decision=DecisionType.REJECT,
            feedback="Empty original query"
        ))

    logger.info(f"sql_regeneration_tool: Starting regeneration for failed SQL: {failed_sql}")
    logger.info(f"sql_regeneration_tool: Failure reason: {failure_reason}")
    logger.info(f"sql_regeneration_tool: Failure type: {failure_type}")

    # Step 1: Generate new SQL with enhanced feedback
    new_sql_result = _generate_regenerated_sql(
        input_data.original_query,
        input_data.context_text,
        input_data.schema_text,
        input_data.previous_chat,
        input_data.failed_sql,
        input_data.failure_reason,
        input_data.failure_type
    )
    
    if not new_sql_result.get("sql_text"):
        return sql_regeneration_output_to_dict(SQLRegenerationOutput(
            original_query=input_data.original_query,
            failed_sql=input_data.failed_sql,
            regenerated_sql="",
            decision=DecisionType.REJECT,
            feedback="Failed to regenerate SQL query"
        ))

    regenerated_sql = new_sql_result["sql_text"]
    logger.info(f"sql_regeneration_tool: Regenerated SQL: {regenerated_sql}")

    # Step 2: Validate the regenerated SQL
    validation_start_time = time.time()
    orchestration_result = validation_orchestrator(
        user_query=input_data.original_query,
        generated_sql=regenerated_sql,
        db_schema=input_data.schema_text,
        context_data=input_data.context_text,
        user_type=input_data.user_type
    )
    validation_time = time.time() - validation_start_time

    # Step 3: Process validation results
    if orchestration_result.get("is_valid", False):
        logger.info("sql_regeneration_tool: Regenerated SQL validation passed, attempting execution")
        return _process_validated_regenerated_sql(regenerated_sql, input_data, orchestration_result)
    else:
        # If regeneration also fails validation, return error
        errors = orchestration_result.get("errors", [])
        return sql_regeneration_output_to_dict(SQLRegenerationOutput(
            original_query=input_data.original_query,
            failed_sql=input_data.failed_sql,
            regenerated_sql=regenerated_sql,
            decision=DecisionType.REJECT,
            feedback=f"Regenerated SQL failed validation: {'; '.join(errors)}",
            validation_time=validation_time,
            validation_strategy=ValidationStrategy(orchestration_result.get("validation_strategy", "sequential"))
        ))


def _generate_regenerated_sql(
    original_query: str,
    context_text: str,
    schema_text: str,
    previous_chat: str,
    failed_sql: str,
    failure_reason: str,
    failure_type: str
) -> Dict[str, str]:
    """
    Generate a new SQL query with enhanced feedback about the failure.
    """
    llm = LLMSession(
        chat_model=current_app.config.get("CHAT_MODEL"),
        embedding_model=current_app.config.get("EMBEDDING_MODEL"),
    )

    # Create specific guidance based on failure type and reason
    specific_guidance = _create_specific_guidance(failure_reason, failure_type)
    
    system_message = (
        "You are an expert DuckDB SQL generator. The previous SQL query failed and needs to be regenerated. "
        "Using ONLY the provided schema and context data, produce a single, executable SQL statement that "
        "accurately answers the user's request.\n\n"
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
        "- DELETE queries: Use for removing records (will require human verification)\n"
        "- DROP queries: Use when user explicitly requests to drop tables/views (will require human verification)\n"
        "- CREATE TABLE queries: Use when user explicitly requests to create a new table\n"
        "- CREATE VIEW queries: Use when user requests to create a view\n"
        "- CREATE INDEX queries: Use when user requests to create an index\n\n"
        "SECURITY GUIDELINES:\n"
        "- Only access tables and columns that exist in the provided schema\n"
        "- Avoid system tables (information_schema, sys.*, pg_catalog) unless user is admin\n"
        "- Do not generate privilege escalation commands (GRANT, REVOKE)\n"
        "- Do not perform file operations (COPY TO, INTO OUTFILE)\n"
        "- Do not execute dangerous functions (xp_cmdshell, exec, system)\n"
        "- Generate only single, focused SQL statements\n"
        "- Admin users have more lenient restrictions for schema-related operations\n\n"
        "TECHNICAL REQUIREMENTS:\n"
        "- Use fully-qualified table names when schema is provided\n"
        "- Add LIMIT 100 for SELECT queries if no explicit limit is specified\n"
        "- Return only the SQL statement; no explanations or comments\n"
        "- Use proper SQL syntax and quoting\n"
        "- Ensure WHERE clauses are properly structured\n"
        "- For case-insensitive string comparisons, use ILIKE instead of = (e.g., WHERE Channel ILIKE 'private label')\n"
        "- For exact case-insensitive matches, use UPPER() or LOWER() functions (e.g., WHERE UPPER(Channel) = UPPER('private label'))\n"
        "- For CREATE TABLE statements, include appropriate data types and constraints\n\n"
        f"REGENERATION CONTEXT:\n"
        f"- Original user query: {original_query}\n"
        f"- Failed SQL query: {failed_sql}\n"
        f"- Failure type: {failure_type}\n"
        f"- Failure reason: {failure_reason}\n\n"
        f"{specific_guidance}\n\n"
        f"CRITICAL: Use the above failure information to generate a corrected query that addresses the specific issue."
    )

    user_message = (
        f"Schema (truncated):\n{schema_text}\n\n"
        f"Context snippets:\n{context_text}\n\n"
        f"Previous chat context:\n{previous_chat}\n\n"
        f"User request:\n{original_query}\n\n"
        f"FAILED SQL QUERY (for reference):\n{failed_sql}\n\n"
        f"FAILURE REASON:\n{failure_reason}"
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


def _create_specific_guidance(failure_reason: str, failure_type: str) -> str:
    """
    Create specific guidance based on the failure reason and type.
    """
    failure_lower = failure_reason.lower()
    
    if failure_type == "execution":
        # Execution failure guidance
        if "can only drop one object at a time" in failure_lower or "multiple drop" in failure_lower:
            return (
                "SPECIFIC REGENERATION INSTRUCTIONS:\n"
                "- The previous query tried to drop multiple tables in a single statement\n"
                "- DuckDB only supports dropping one object at a time\n"
                "- Generate separate DROP statements for each table\n"
                "- Example: Instead of 'DROP TABLE t1, t2, t3;', use:\n"
                "  DROP TABLE t1;\n"
                "  DROP TABLE t2;\n"
                "  DROP TABLE t3;\n"
                "- Or use a single DROP statement for the most important table first\n"
            )
        elif "table" in failure_lower and ("not found" in failure_lower or "unknown" in failure_lower):
            return (
                "SPECIFIC REGENERATION INSTRUCTIONS:\n"
                "- The previous query referenced a table that doesn't exist\n"
                "- Check the schema carefully for correct table names\n"
                "- Use fully qualified names (schema.table) if schema is provided\n"
                "- Look for similar table names in the schema\n"
                "- Verify table name spelling and case sensitivity\n"
            )
        elif "column" in failure_lower and ("not found" in failure_lower or "unknown" in failure_lower):
            return (
                "SPECIFIC REGENERATION INSTRUCTIONS:\n"
                "- The previous query referenced a column that doesn't exist\n"
                "- Check the schema for correct column names\n"
                "- Use table aliases if needed to avoid ambiguity\n"
                "- Verify column name spelling and case sensitivity\n"
            )
        elif "syntax error" in failure_lower or "invalid" in failure_lower:
            return (
                "SPECIFIC REGENERATION INSTRUCTIONS:\n"
                "- The previous query had syntax errors\n"
                "- Check for missing semicolons, parentheses, or keywords\n"
                "- Verify proper SQL syntax for the specific operation\n"
                "- Ensure proper clause ordering (SELECT, FROM, WHERE, GROUP BY, etc.)\n"
            )
        elif "group" in failure_lower and "by" in failure_lower:
            return (
                "SPECIFIC REGENERATION INSTRUCTIONS:\n"
                "- The previous query had GROUP BY clause issues\n"
                "- All non-aggregated columns in SELECT must appear in GROUP BY\n"
                "- Or use aggregate functions (COUNT, SUM, AVG, etc.) for non-grouped columns\n"
                "- Check for proper HAVING clause usage with GROUP BY\n"
            )
        else:
            return (
                "SPECIFIC REGENERATION INSTRUCTIONS:\n"
                "- The previous SQL query failed execution\n"
                "- Analyze the error message and fix the specific issue\n"
                "- Check table names, column names, and syntax\n"
                "- Ensure the query follows proper SQL standards\n"
                "- Verify that all referenced objects exist in the schema\n"
            )
    else:
        # Validation failure guidance
        if "vague" in failure_lower or "clarification" in failure_lower:
            return (
                "SPECIFIC REGENERATION INSTRUCTIONS:\n"
                "- The previous query was too vague\n"
                "- Use available context and schema more aggressively\n"
                "- Make reasonable assumptions about table names and relationships\n"
                "- Look for similar table names in the schema\n"
                "- Use context data to infer missing details\n"
            )
        elif "schema" in failure_lower or "validation" in failure_lower:
            return (
                "SPECIFIC REGENERATION INSTRUCTIONS:\n"
                "- The previous query failed schema validation\n"
                "- Check the schema carefully for correct table and column names\n"
                "- Use fully qualified names (schema.table) if schema is provided\n"
                "- Verify table name spelling and case sensitivity\n"
                "- Ensure all referenced objects exist in the schema\n"
            )
        elif "security" in failure_lower or "injection" in failure_lower:
            return (
                "SPECIFIC REGENERATION INSTRUCTIONS:\n"
                "- The previous query was flagged for security concerns\n"
                "- Avoid system tables unless user is admin\n"
                "- Do not use dangerous functions or operations\n"
                "- Ensure the query only accesses legitimate data\n"
                "- Use proper SQL syntax without injection patterns\n"
            )
        else:
            return (
                "SPECIFIC REGENERATION INSTRUCTIONS:\n"
                "- The previous SQL query failed validation\n"
                "- Analyze the validation error and fix the specific issue\n"
                "- Check table names, column names, and syntax\n"
                "- Ensure the query follows proper SQL standards\n"
                "- Verify that all referenced objects exist in the schema\n"
            )


def _process_validated_regenerated_sql(
    regenerated_sql: str,
    input_data: SQLRegenerationInput,
    orchestration_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process validated regenerated SQL and execute if accepted.
    """
    # Check guardrail decision from orchestration results
    guardrail_result = orchestration_result.get("validation_results", {}).get("guardrail", {}).get("result", {})
    decision = guardrail_result.get("decision", "reject")
    feedback = guardrail_result.get("feedback", "")
    
    if decision == "accept":
        try:
            # Execute the regenerated query
            rows = execute_sql_query(regenerated_sql)
            return sql_regeneration_output_to_dict(SQLRegenerationOutput(
                original_query=input_data.original_query,
                failed_sql=input_data.failed_sql,
                regenerated_sql=regenerated_sql,
                decision=DecisionType.ACCEPT,
                feedback=f"Successfully regenerated and executed query. {feedback}",
                row_count=len(rows),
                rows=rows,
                validation_time=orchestration_result.get("total_validation_time", 0),
                validation_strategy=ValidationStrategy(orchestration_result.get("validation_strategy", "sequential"))
            ))
        except Exception as e:
            # Analyze the execution failure of the regenerated query
            logger.info(f"Regenerated SQL execution failed, analyzing error: {str(e)}")
            analysis_result = sql_execution_analyzer(
                sql_query=regenerated_sql,
                error_message=str(e),
                user_query=input_data.original_query,
                db_schema=input_data.schema_text
            )
            
            failure_type = analysis_result.get("failure_type", "unknown")
            should_regenerate = analysis_result.get("should_regenerate", False)
            regeneration_feedback = analysis_result.get("regeneration_feedback", "")
            user_friendly_message = analysis_result.get("user_friendly_message", "")
            
            if should_regenerate and failure_type == "sql_structure":
                # Return regeneration request for SQL structure errors
                logger.info(f"Regenerated SQL structure error detected, requesting another regeneration: {regeneration_feedback}")
                return {
                    "type": "regeneration_request",
                    "sql": regenerated_sql,
                    "feedback": regeneration_feedback,
                    "requires_clarification": False,
                    "original_query": input_data.original_query,
                    "user_friendly_message": user_friendly_message,
                    "technical_details": analysis_result.get("technical_details", ""),
                    "suggested_fixes": analysis_result.get("suggested_fixes", []),
                    "message": f"Regenerated SQL execution failed due to a structural issue. I'll try to fix it.\n\n**Error:** {user_friendly_message}\n\n**Technical Details:** {analysis_result.get('technical_details', '')}\n\nI'm regenerating the query with the following feedback: {regeneration_feedback}"
                }
            else:
                # Return user-friendly error message for valid execution failures
                logger.info(f"Regenerated SQL valid execution failure: {user_friendly_message}")
                return sql_regeneration_output_to_dict(SQLRegenerationOutput(
                    original_query=input_data.original_query,
                    failed_sql=input_data.failed_sql,
                    regenerated_sql=regenerated_sql,
                    decision=DecisionType.EXECUTION_FAILED,
                    feedback=user_friendly_message,
                    validation_time=orchestration_result.get("total_validation_time", 0),
                    validation_strategy=ValidationStrategy(orchestration_result.get("validation_strategy", "sequential"))
                ))
    elif decision == "human_verification":
        # Return human verification request with the regenerated SQL query
        return {
            "type": "human_verification",
            "sql": regenerated_sql,
            "feedback": feedback,
            "requires_clarification": False,  # This is execution confirmation, not clarification
            "original_query": input_data.original_query,
            "message": f"I've regenerated a SQL query for you. Would you like me to execute it?\n\nSQL Query:\n{regenerated_sql}\n\n**Reasoning:** {feedback}\n\nPlease respond with \"yes\" to execute or \"no\" to cancel."
        }
    else:
        return sql_regeneration_output_to_dict(SQLRegenerationOutput(
            original_query=input_data.original_query,
            failed_sql=input_data.failed_sql,
            regenerated_sql=regenerated_sql,
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
