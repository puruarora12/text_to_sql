from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict, Any, List
import re

from app import logger
from app.services.datastore.duckdb_datastore import DuckDBDatastore
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
            
            return sql_execution_output_to_dict(SQLExecutionOutput(
                query=input_data.sql_query,
                decision=DecisionType.EXECUTED_AFTER_VERIFICATION,
                feedback="Query executed successfully after user confirmation",
                row_count=len(rows),
                rows=rows,
                user_response=input_data.user_response
            ))
            
        except Exception as e:
            logger.error(f"sql_execution_handler: Execution failed: {e}")
            return sql_execution_output_to_dict(SQLExecutionOutput(
                query=input_data.sql_query,
                decision=DecisionType.REJECT,
                feedback=f"Execution failed: {str(e)}",
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
