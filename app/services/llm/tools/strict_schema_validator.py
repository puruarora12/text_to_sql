from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict, Any, List, Set
import re

from app import logger
from app.services.datastore.duckdb_datastore import DuckDBDatastore
from app.services.llm.session import LLMSession
from flask import current_app

import json


@tool_call
@observe
def strict_schema_validator(
    sql_query: str,
    db_schema: str,
    user_query: str
) -> Dict[str, Any]:
    """
    Strictly validate SQL query against actual database schema.
    
    Args:
        sql_query: The SQL query to validate
        db_schema: Schema information from db_schema_vector_search
        user_query: Original user query for context
        
    Returns:
        {
            "is_valid": bool,
            "validation_result": "pass|fail|clarification_needed",
            "issues": [list of specific issues],
            "suggestions": [list of suggestions],
            "missing_tables": [list of non-existent tables],
            "missing_columns": [list of non-existent columns],
            "feedback": "detailed explanation"
        }
    """
    if not sql_query:
        return {
            "is_valid": False,
            "validation_result": "fail",
            "issues": ["Empty SQL query"],
            "suggestions": ["Please provide a valid SQL query"],
            "missing_tables": [],
            "missing_columns": [],
            "feedback": "No SQL query provided for validation"
        }
    
    try:
        # Step 1: Extract table and column references from SQL
        extracted_refs = _extract_schema_references(sql_query)
        
        # Step 2: Get actual database schema
        actual_schema = _get_actual_database_schema()
        
        # Step 3: Validate references against actual schema
        validation_result = _validate_schema_references(
            extracted_refs, actual_schema, user_query
        )
        
        # Step 4: Use LLM for context-aware validation
        llm_validation = _llm_schema_validation(
            sql_query, db_schema, user_query, validation_result
        )
        
        # Step 5: Combine results
        final_result = _combine_validation_results(validation_result, llm_validation)
        
        logger.info(f"Schema validation result: {final_result['validation_result']}")
        return final_result
        
    except Exception as e:
        logger.error(f"Error in strict schema validation: {e}")
        return {
            "is_valid": False,
            "validation_result": "fail",
            "issues": [f"Validation error: {str(e)}"],
            "suggestions": ["Please check your query and try again"],
            "missing_tables": [],
            "missing_columns": [],
            "feedback": f"Schema validation failed due to error: {str(e)}"
        }


def _extract_schema_references(sql_query: str) -> Dict[str, Any]:
    """
    Extract table and column references from SQL query.
    """
    sql_lower = sql_query.lower()
    
    # Extract table references
    table_patterns = [
        r'from\s+([a-zA-Z_][a-zA-Z0-9_]*\.?[a-zA-Z_][a-zA-Z0-9_]*)',
        r'join\s+([a-zA-Z_][a-zA-Z0-9_]*\.?[a-zA-Z_][a-zA-Z0-9_]*)',
        r'update\s+([a-zA-Z_][a-zA-Z0-9_]*\.?[a-zA-Z_][a-zA-Z0-9_]*)',
        r'insert\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*\.?[a-zA-Z_][a-zA-Z0-9_]*)',
        r'delete\s+from\s+([a-zA-Z_][a-zA-Z0-9_]*\.?[a-zA-Z_][a-zA-Z0-9_]*)'
    ]
    
    tables = set()
    for pattern in table_patterns:
        matches = re.findall(pattern, sql_lower)
        for match in matches:
            # Clean up table name
            table_name = match.strip()
            if '.' in table_name:
                # Remove schema prefix if present
                table_name = table_name.split('.')[-1]
            tables.add(table_name)
    
    # Extract column references
    column_patterns = [
        r'select\s+(.*?)\s+from',
        r'where\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[=<>!]',
        r'group\s+by\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'order\s+by\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'update\s+.*?\s+set\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*='
    ]
    
    columns = set()
    for pattern in column_patterns:
        matches = re.findall(pattern, sql_lower)
        for match in matches:
            # Handle multiple columns in SELECT clause
            if ',' in match:
                col_list = [col.strip() for col in match.split(',')]
                for col in col_list:
                    # Skip functions and expressions
                    if '(' not in col and not col.startswith(('count', 'sum', 'avg', 'max', 'min')):
                        columns.add(col)
            else:
                # Skip functions and expressions
                if '(' not in match and not match.startswith(('count', 'sum', 'avg', 'max', 'min')):
                    columns.add(match.strip())
    
    return {
        "tables": list(tables),
        "columns": list(columns)
    }


def _get_actual_database_schema() -> Dict[str, Any]:
    """
    Get actual database schema from DuckDB.
    """
    try:
        datastore = DuckDBDatastore(database="app/data/data.db")
        tables = datastore.get_list_of_tables()
        
        schema_info = {
            "tables": {},
            "all_tables": set(),
            "all_columns": set()
        }
        
        for table_info in tables:
            table_name = table_info.get("table_name", "")
            schema_name = table_info.get("table_schema", "")
            
            # Get columns for this table
            columns = datastore.get_list_of_columns(table_name, schema_name)
            column_names = [col.get("column_name", "") for col in columns]
            
            # Store table info
            full_table_name = f"{schema_name}.{table_name}" if schema_name else table_name
            schema_info["tables"][full_table_name] = {
                "columns": column_names,
                "schema": schema_name,
                "name": table_name
            }
            
            # Add to sets for quick lookup
            schema_info["all_tables"].add(table_name.lower())
            schema_info["all_tables"].add(full_table_name.lower())
            
            for col in column_names:
                schema_info["all_columns"].add(col.lower())
        
        return schema_info
        
    except Exception as e:
        logger.error(f"Error getting database schema: {e}")
        return {
            "tables": {},
            "all_tables": set(),
            "all_columns": set()
        }


def _validate_schema_references(
    extracted_refs: Dict[str, Any],
    actual_schema: Dict[str, Any],
    user_query: str
) -> Dict[str, Any]:
    """
    Validate extracted references against actual schema.
    """
    missing_tables = []
    missing_columns = []
    issues = []
    suggestions = []
    
    # Validate tables
    for table in extracted_refs["tables"]:
        if table.lower() not in actual_schema["all_tables"]:
            missing_tables.append(table)
            issues.append(f"Table '{table}' does not exist in the database")
    
    # Validate columns (basic check - we'll do more detailed validation with LLM)
    for column in extracted_refs["columns"]:
        if column.lower() not in actual_schema["all_columns"]:
            missing_columns.append(column)
            issues.append(f"Column '{column}' does not exist in any table")
    
    # Generate suggestions
    if missing_tables:
        suggestions.append(f"Available tables: {', '.join(sorted(actual_schema['all_tables']))}")
    
    if missing_columns:
        suggestions.append("Please check column names against the actual schema")
    
    return {
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "issues": issues,
        "suggestions": suggestions,
        "extracted_refs": extracted_refs,
        "actual_schema": actual_schema
    }


def _llm_schema_validation(
    sql_query: str,
    db_schema: str,
    user_query: str,
    validation_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Use LLM for context-aware schema validation.
    """
    try:
        llm = LLMSession(
            chat_model=current_app.config.get("CHAT_MODEL"),
            embedding_model=current_app.config.get("EMBEDDING_MODEL"),
        )
        
        # Prepare context for LLM
        missing_tables = validation_result.get("missing_tables", [])
        missing_columns = validation_result.get("missing_columns", [])
        
        system_message = (
            "You are a database schema validation expert. Analyze the SQL query against the provided schema.\n\n"
            "Your task is to:\n"
            "1. Check if the SQL query matches the user's intent\n"
            "2. Validate that all tables and columns exist in the schema\n"
            "3. Identify any schema mismatches or missing elements\n"
            "4. Provide helpful suggestions for clarification\n\n"
            "Validation rules:\n"
            "- If tables/columns don't exist, suggest clarification\n"
            "- If the query doesn't match user intent, suggest clarification\n"
            "- If everything is valid, confirm the query is correct\n\n"
            "Respond with JSON:\n"
            "{\n"
            '  "validation_result": "pass|clarification_needed|fail",\n'
            '  "issues": ["list of specific issues"],\n'
            '  "suggestions": ["list of helpful suggestions"],\n'
            '  "feedback": "detailed explanation",\n'
            '  "needs_clarification": true/false\n'
            "}"
        )
        
        user_message = (
            f"User Query: {user_query}\n\n"
            f"Generated SQL: {sql_query}\n\n"
            f"Database Schema:\n{db_schema}\n\n"
            f"Validation Issues Found:\n"
            f"- Missing tables: {missing_tables}\n"
            f"- Missing columns: {missing_columns}\n\n"
            "Please validate this SQL query against the schema and user intent."
        )
        
        response = llm.chat(
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ]
        )
        content = response.choices[0].message.content or ""
        
        # Parse JSON response
        try:
            # Extract JSON from response if wrapped in code blocks
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
            if json_match:
                content = json_match.group(1)
            
            # Also try to extract JSON if just wrapped in ```
            if not json_match:
                json_match = re.search(r"```\s*([\s\S]*?)\s*```", content)
                if json_match:
                    content = json_match.group(1)
            
            parsed = json.loads(content)
            
            return {
                "validation_result": parsed.get("validation_result", "fail"),
                "issues": parsed.get("issues", []),
                "suggestions": parsed.get("suggestions", []),
                "feedback": parsed.get("feedback", ""),
                "needs_clarification": parsed.get("needs_clarification", False)
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response: {content}")
            
            # Fallback: check if response indicates issues
            if any(keyword in content.lower() for keyword in ["missing", "doesn't exist", "invalid", "error"]):
                return {
                    "validation_result": "clarification_needed",
                    "issues": ["Schema validation issues detected"],
                    "suggestions": ["Please check table and column names"],
                    "feedback": content[:500],
                    "needs_clarification": True
                }
            else:
                return {
                    "validation_result": "pass",
                    "issues": [],
                    "suggestions": [],
                    "feedback": "Schema validation passed",
                    "needs_clarification": False
                }
                
    except Exception as e:
        logger.error(f"Error in LLM schema validation: {e}")
        return {
            "validation_result": "fail",
            "issues": [f"LLM validation error: {str(e)}"],
            "suggestions": ["Please try again"],
            "feedback": f"Schema validation failed: {str(e)}",
            "needs_clarification": False
        }


def _combine_validation_results(
    validation_result: Dict[str, Any],
    llm_validation: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Combine technical validation with LLM validation results.
    """
    # If technical validation found missing tables/columns, that takes precedence
    if validation_result.get("missing_tables") or validation_result.get("missing_columns"):
        return {
            "is_valid": False,
            "validation_result": "clarification_needed",
            "issues": validation_result.get("issues", []) + llm_validation.get("issues", []),
            "suggestions": validation_result.get("suggestions", []) + llm_validation.get("suggestions", []),
            "missing_tables": validation_result.get("missing_tables", []),
            "missing_columns": validation_result.get("missing_columns", []),
            "feedback": f"Schema validation failed. {llm_validation.get('feedback', '')}"
        }
    
    # Otherwise, use LLM validation result
    is_valid = llm_validation.get("validation_result") == "pass"
    
    return {
        "is_valid": is_valid,
        "validation_result": llm_validation.get("validation_result", "fail"),
        "issues": llm_validation.get("issues", []),
        "suggestions": llm_validation.get("suggestions", []),
        "missing_tables": validation_result.get("missing_tables", []),
        "missing_columns": validation_result.get("missing_columns", []),
        "feedback": llm_validation.get("feedback", "")
    }
