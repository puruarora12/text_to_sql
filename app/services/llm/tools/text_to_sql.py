from langfuse.decorators import observe
from vaul import tool_call

from app import logger
from app.services.datastore.duckdb_datastore import DuckDBDatastore
from app.services.llm.structured_outputs.text_to_sql import SqlQuery


@tool_call
@observe
def text_to_sql(query: str) -> str:
    """A tool for converting natural language queries to SQL queries and executing them.
    
    This tool analyzes the available database schema and generates appropriate SQL
    queries based on natural language input.
    """

    logger.info(f"Text-to-SQL tool called with natural language query: '{query}'")
    
    # Initialize the DuckDB datastore
    datastore = DuckDBDatastore(
        database="app/data/data.db"
    )
    
    logger.info(f"DuckDB datastore initialized with database: app/data/data.db")

    # Get available tables and their schemas
    available_tables = {}
    try:
        logger.info("Discovering database schema...")
        tables_result = datastore.list_tables()
        logger.info(f"Found {len(tables_result)} tables in database")
        
        # Get schema for each table
        for _, row in tables_result.iterrows():
            schema_name = row[0] if len(row) > 1 else 'main'
            table_name = row[1] if len(row) > 1 else row[0]
            
            try:
                columns_info = datastore.get_columns(table_name, schema_name)
                available_tables[f"{schema_name}.{table_name}"] = {
                    "columns": columns_info.to_dict('records') if not columns_info.empty else [],
                    "full_name": f"{schema_name}.{table_name}",
                    "short_name": table_name
                }
                logger.info(f"Schema loaded for {schema_name}.{table_name}: {len(columns_info)} columns")
                
            except Exception as schema_error:
                logger.warning(f"Could not get schema for {schema_name}.{table_name}: {schema_error}")
                
    except Exception as table_error:
        logger.error(f"Could not discover database schema: {table_error}")
        return f"Error discovering database schema: {str(table_error)}"

    if not available_tables:
        logger.warning("No accessible tables found in database")
        return "No accessible tables found in the database."

    # Build schema context for LLM
    schema_context = "Available tables and their schemas:\n"
    for table_name, table_info in available_tables.items():
        schema_context += f"\nTable: {table_name}\n"
        schema_context += "Columns:\n"
        for col in table_info["columns"]:
            col_name = col.get("column_name", "unknown")
            data_type = col.get("data_type", "unknown")
            schema_context += f"  - {col_name}: {data_type}\n"
    
    logger.info("Generating SQL using LLM with schema context")
    
    # Use LLM to generate proper SQL based on schema
    from app.services.llm.session import LLMSession
    from flask import current_app
    
    llm = LLMSession(
        chat_model=current_app.config.get("CHAT_MODEL", "gpt-4o-mini"),
        embedding_model=current_app.config.get("EMBEDDING_MODEL", "text-embedding-3-small")
    )
    
    sql_generation_messages = [
        {
            "role": "system",
            "content": (
                "You are a SQL expert. Generate a SQL query based on the natural language request and the provided database schema.\n"
                "Rules:\n"
                "1. Use ONLY the tables and columns that exist in the schema\n"
                "2. Use proper SQL syntax for DuckDB\n"
                "3. Return ONLY the SQL query, no explanations\n"
                "4. Use appropriate JOINs if multiple tables are needed\n"
                "5. Handle date/time operations properly\n"
                "6. If the request cannot be fulfilled with available data, return: SELECT 'Data not available for this query' as message;\n"
            )
        },
        {
            "role": "user", 
            "content": f"Database Schema:\n{schema_context}\n\nNatural Language Query: {query}\n\nGenerate the SQL query:"
        }
    ]
    
    try:
        logger.info("Requesting SQL generation from LLM...")
        response = llm.chat(messages=sql_generation_messages)
        generated_sql = response.choices[0].message.content.strip()
        
        # Clean up the SQL (remove markdown formatting if present)
        if generated_sql.startswith("```sql"):
            generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
        elif generated_sql.startswith("```"):
            generated_sql = generated_sql.replace("```", "").strip()
            
        logger.info(f"LLM generated SQL: {generated_sql}")
        
        # Execute the generated SQL
        result = datastore.execute(generated_sql)
        
        logger.info(f"Query executed successfully. Result shape: {result.shape if hasattr(result, 'shape') else 'unknown'}")
        
        # Return the result as markdown
        if result is not None and not result.empty:
            markdown_result = result.to_markdown(index=False, floatfmt=".2f")
            logger.info(f"Returning markdown result (length: {len(markdown_result)})")
            return markdown_result
        else:
            logger.info("Query returned no results")
            return "Query executed successfully but returned no results."
        
    except Exception as e:
        logger.error(f"Error in SQL generation or execution: {e}")
        logger.error(f"Generated SQL that failed: {generated_sql if 'generated_sql' in locals() else 'N/A'}")
        
        # Fallback: try to provide helpful information about available tables
        table_list = "\n".join([f"- {name}" for name in available_tables.keys()])
        return f"Error processing query: {str(e)}\n\nAvailable tables:\n{table_list}"