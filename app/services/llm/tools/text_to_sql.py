from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict
import re

from app import logger
from app.services.datastore.duckdb_datastore import DuckDBDatastore


@tool_call
@observe
def text_to_sql(sql: str, context_text: str, schema_text: str) -> Dict[str, str]:
    """Tool: Accepts a user request and returns a SQL query.

    The LLM is responsible for generating SQL using the RAG context and database schema provided in the chat messages.
    This tool performs light normalization (e.g., stripping code fences) and returns {"query": sql_text}.
    """
    logger.info("text_to_sql tool invoked")
    sql_text = _extract_sql_from_text(sql or "")
    logger.info(f"SQL text: {sql_text}")
    return {"query": sql_text}


def db_schema_vector_search(user_request: str) -> Dict[str, str]:
    context_text = ""
    try:
        from app.services.vector_store.vector_store_service import VectorStoreService
        vector_store = VectorStoreService(collection_name="dbschema", index_name="dbschema")
        vector_results = vector_store.search(user_request, n_results=2) if user_request else []
        # logger.info(f"Vector results: {vector_results}")
        
        # Build concise lines with [schema.table] - Description
        for item in vector_results:
            lines = item.get("metadata", "").get("text", "")
            context_text= context_text + lines
    except Exception as e:
        logger.info(f"Exception in vector search: {e}")
        context_text = ""

    # Build compact database schema text (limited size)
    schema_text = ""
    try:
        datastore = DuckDBDatastore(database="app/data/data.db")
        tables = datastore.get_list_of_tables()
        lines = []
        max_tables = 8
        for i, t in enumerate(tables[:max_tables]):
            tbl = t.get("table_name", "")
            sch = t.get("table_schema", "")
            columns = datastore.get_list_of_columns(tbl, sch)
            col_parts = [
                f"{c.get('column_name')} {c.get('data_type')}"
                + (" NOT NULL" if c.get("is_nullable") == "NO" else "")
                for c in columns[:10]
            ]
            header = f"[{sch + '.' if sch else ''}{tbl}]"
            lines.append(header + ("\n  - " + "\n  - ".join(col_parts) if col_parts else ""))
        schema_text = "\n\n".join(lines)
        
    except Exception:
        schema_text = ""
    return context_text, schema_text


def _extract_sql_from_text(text: str) -> str:
    """Extract SQL from model output, handling optional code fences."""
    if not text:
        return ""
    # Prefer ```sql blocks
    match = re.search(r"```sql\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Any code block
    match = re.search(r"```\s*([\s\S]*?)\s*```", text)
    if match:
        return match.group(1).strip()
    return text.strip()