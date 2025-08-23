from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict, Any, List
import re

from app import logger
from app.services.datastore.duckdb_datastore import DuckDBDatastore
from app.services.llm.tools.sql_execution_analyzer import sql_execution_analyzer
from app.controllers.scan_controller import ScanController
from app.schemas.tool_schemas import (
    SQLExecutionInput, SQLExecutionOutput, DecisionType,
    dict_to_sql_execution_input, sql_execution_output_to_dict
)


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
def sql_execution_handler(sql_query: str, user_response: str, original_feedback: str = "") -> Dict[str, Any]:
    """
    Handle SQL execution confirmation (yes/no responses) without regenerating SQL.
    
    Args:
        sql_query: The SQL query to execute
        user_response: User's response ("yes", "no", or similar)
        original_feedback: Original feedback/reasoning for the query
        
    Returns:
        Execution result or cancellation confirmation
    """
    # Convert input to structured format
    input_data = SQLExecutionInput(
        sql_query=sql_query,
        user_response=user_response,
        original_feedback=original_feedback
    )
    
    # Normalize user response
    user_response_lower = input_data.user_response.lower().strip()
    
    # Check if user wants to execute
    if user_response_lower in ["yes", "y", "execute", "run", "ok", "sure", "proceed"]:
        logger.info(f"sql_execution_handler: User confirmed execution of SQL: {input_data.sql_query}")
        
        try:
            # Execute the SQL query
            rows = execute_sql_query(input_data.sql_query)
            
            # Check if this is a CREATE statement and trigger automatic scan
            sql_lower = input_data.sql_query.lower().strip()
            is_create_statement = sql_lower.startswith("create")
            
            logger.info(f"SQL execution completed. SQL: {input_data.sql_query[:100]}...")
            logger.info(f"Is CREATE statement: {is_create_statement}")
            
            feedback = "Query executed successfully after user confirmation"
            
            # Add scan notification to feedback if it's a CREATE statement
            if is_create_statement:
                logger.info("CREATE statement detected in execution handler, triggering automatic scan...")
                try:
                    # Trigger automatic scan to update schema information
                    scan_controller = ScanController()
                    scan_result = scan_controller.get_tables()
                    logger.info(f"Automatic scan completed successfully. Found {len(scan_result)} tables")
                    feedback += "\n\n✅ Table created successfully! The database schema has been automatically updated."
                    logger.info("Automatic scan triggered after CREATE statement execution in handler")
                except Exception as scan_error:
                    logger.warning(f"Automatic scan failed after CREATE statement in handler: {scan_error}")
                    feedback += "\n\n✅ Table created successfully! (Schema scan failed, but table was created)"
            
            return sql_execution_output_to_dict(SQLExecutionOutput(
                query=input_data.sql_query,
                decision=DecisionType.EXECUTED_AFTER_VERIFICATION,
                feedback=feedback,
                row_count=len(rows),
                rows=rows,
                user_response=input_data.user_response
            ))
            
        except Exception as e:
            logger.error(f"sql_execution_handler: Execution failed: {e}")
            
            # Analyze the execution failure using the SQL execution analyzer
            analysis_result = sql_execution_analyzer(
                sql_query=input_data.sql_query,
                error_message=str(e),
                user_query=f"User confirmed execution of: {input_data.sql_query}",  # Context about the query
                db_schema=""  # Schema not available in this context
            )
            
            failure_type = analysis_result.get("failure_type", "unknown")
            should_regenerate = analysis_result.get("should_regenerate", False)
            regeneration_feedback = analysis_result.get("regeneration_feedback", "")
            user_friendly_message = analysis_result.get("user_friendly_message", "")
            
            if should_regenerate and failure_type == "sql_structure":
                # Return regeneration request for SQL structure errors
                logger.info(f"SQL structure error detected in execution handler, requesting regeneration: {regeneration_feedback}")
                return {
                    "type": "regeneration_request",
                    "sql": input_data.sql_query,
                    "feedback": regeneration_feedback,
                    "requires_clarification": False,
                    "original_query": f"User confirmed execution of: {input_data.sql_query}",
                    "user_friendly_message": user_friendly_message,
                    "technical_details": analysis_result.get("technical_details", ""),
                    "suggested_fixes": analysis_result.get("suggested_fixes", []),
                    "message": f"SQL execution failed due to a structural issue. I'll try to fix it.\n\n**Error:** {user_friendly_message}\n\n**Technical Details:** {analysis_result.get('technical_details', '')}\n\nI'm regenerating the query with the following feedback: {regeneration_feedback}",
                    "user_response": input_data.user_response
                }
            else:
                # Return user-friendly error message for valid execution failures
                logger.info(f"Valid execution failure in execution handler: {user_friendly_message}")
                return sql_execution_output_to_dict(SQLExecutionOutput(
                    query=input_data.sql_query,
                    decision=DecisionType.REJECT,
                    feedback=user_friendly_message,
                    user_response=input_data.user_response
                ))
    
    # Check if user wants to cancel
    elif user_response_lower in ["no", "n", "cancel", "stop", "abort", "don't", "dont"]:
        logger.info(f"sql_execution_handler: User cancelled execution of SQL: {input_data.sql_query}")
        
        return sql_execution_output_to_dict(SQLExecutionOutput(
            query=input_data.sql_query,
            decision=DecisionType.CANCELLED_BY_USER,
            feedback="Query execution cancelled by user",
            user_response=input_data.user_response
        ))
    
    # Ambiguous response
    else:
        logger.warning(f"sql_execution_handler: Ambiguous user response: '{input_data.user_response}'")
        
        return sql_execution_output_to_dict(SQLExecutionOutput(
            query=input_data.sql_query,
            decision=DecisionType.HUMAN_VERIFICATION,
            feedback=f"Please respond with 'yes' to execute or 'no' to cancel. Your response '{input_data.user_response}' was not clear.",
            user_response=input_data.user_response
        ))
