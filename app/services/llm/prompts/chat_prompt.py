from app.services.llm.prompts import prompt



@prompt()
def chat_prompt(**kwargs) -> list:
    """
    Build a SQL-generation chat prompt using RAG context from the vector store.

    Args:
        context_text: Concise schema/documentation snippets retrieved from vector search
        user_request: The user's natural language question

    Returns:
        A list of chat messages guiding the model to produce a single SQL statement.
    """
    system_instructions = (
        "You are a helpful assistant with access to function tools. "
        "Always use available tools to accomplish tasks when appropriate. "
        "If the user requests SQL generation, data retrieval, or analytics from the database, "
        "call the function tool `text_to_sql` with the argument {sql: '<your SQL here>'} to return the SQL. "
        "Do not print SQL directly in the message; rely on the tool call.\n\n"
        "When generating SQL, behave as a senior DuckDB SQL engineer: "
        "Using ONLY the provided schema/documentation snippets, generate a single, valid, and executable DuckDB SQL statement that answers the user's request. "
        "Constraints: "
        "(1) The SQL must be read-only (CTEs and SELECT only; no DDL/DML), "
        "(2) Use exact table/column names from snippets; prefer fully-qualified schema.table when a schema is given, "
        "(3) Include appropriate JOINs, WHERE, GROUP BY, ORDER BY as needed, "
        "(4) If the user did not specify a limit, append LIMIT 100, "
        "(5) If context lacks exact fields, choose the closest semantically relevant columns and avoid Cartesian products."
    )

    user_content = (
        "If you need database context/snippets, first call the function tool `db_schema_vector_search` with {natural_language_query: '<the user request>'}. "
        "Use the returned context_text and schema_text to plan the SQL. "
        "Generate a SQL candidate and call the function tool `sql_guardrail` with {sql, schema_text, context_text}. "
        "If accept=false, use the feedback to revise and try again. When acceptable, call `text_to_sql` with {sql: '<your SQL>'}.\n\n"
        "Guidelines:\n"
        "- Ensure identifiers match the snippets exactly (respect case if shown).\n"
        "- Prefer ISO date/time filters and consistent aliases.\n"
        "- Avoid SELECT *. Select only needed columns when reasonable.\n"
        "- Limit the number of rows returned to 100 unless the user asks for more.\n"
        "- If multiple tables look similar, choose the one with columns most aligned to the request.\n"
        "- If the request is time-based, order by a relevant timestamp descending.\n"
        "- If you must infer joins, join on plausible keys (e.g., *_id to id) from the snippets.\n"
        "- Do not include any explanations or markdown—output the SQL only."
    )

    return [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": user_content},
    ]
