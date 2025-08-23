import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4
from flask import current_app
from config import config
from app.services.datastore.duckdb_datastore import DuckDBDatastore
from app.services.llm.session import LLMSession
from app.services.llm.structured_outputs.table_doc import TableDoc
from app.services.vector_store.vector_store import CatalogItem, DuckDBVectorStore
from app import logger


class TableCatalogService:
    def __init__(self, database_path: str = "app/data/data.db") -> None:
        self.database_path = database_path
        self.datastore = DuckDBDatastore(database=database_path)
        self.vector_store = DuckDBVectorStore(db_path=database_path)

    def _build_table_profile_text(
        self,
        schema_name: Optional[str],
        table_name: str,
        columns: List[Dict[str, Any]],
        sample_rows: List[Dict[str, Any]],
    ) -> str:
        lines: List[str] = []
        fq = f"{schema_name}.{table_name}" if schema_name else table_name
        lines.append(f"Table: {fq}")
        lines.append("Columns:")
        for col in columns:
            col_name = col.get("column_name")
            data_type = col.get("data_type")
            lines.append(f"- {col_name}: {data_type}")
        if sample_rows:
            lines.append("Sample Rows (up to 5):")
            for row in sample_rows[:5]:
                lines.append(json.dumps(row, ensure_ascii=False))
        # logger.info(f"lines: {lines}")
        return "\n".join(lines)

    def scan_and_index(
        self, limit_rows: int = 5, schema_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        tables_df = self.datastore.list_tables(schema_name=schema_filter)
        tables = [
            {
                "schema_name": r[0],
                "table_name": r[1],
            }
            for r in tables_df.itertuples(index=False)
        ]
        tables = tables[:1]
        chat_model = current_app.config.get("CHAT_MODEL")
        embedding_model = current_app.config.get("EMBEDDING_MODEL")
        
        # For table documentation, prefer OpenAI models for better structured output support
        if chat_model and "anthropic" in chat_model.lower():
            logger.info(f"Detected Anthropic model {chat_model}, switching to gpt-4o-mini for better structured output")
            chat_model = "gpt-4o-mini"
        
        llm = LLMSession(
            chat_model=chat_model,
            embedding_model=embedding_model,
        )
        logger.info(f"Using models - Chat: {llm.chat_model}, Embedding: {llm.embedding_model}")
        logger.info(f"Tables retrieved: {tables}")
        indexed = 0
        failures: List[str] = []
        items: List[CatalogItem] = []

        for t in tables:
            schema_name = t.get("schema_name")
            table_name = t.get("table_name")
            try:
                cols_df = self.datastore.get_columns(table_name, schema_name=schema_name)
                cols = [
                    {
                        "column_name": c[0],
                        "data_type": c[1],
                        "is_nullable": c[2],
                        "character_maximum_length": c[3],
                    }
                    for c in cols_df.itertuples(index=False)
                ]

                sample_df = self.datastore.get_sample_data(
                    table_name, limit=limit_rows, schema_name=schema_name
                )
                # Convert to records and handle non-serializable types like timestamps
                sample_rows = []
                for _, row in sample_df.iterrows():
                    row_dict = {}
                    for col, val in row.items():
                        # Convert timestamps and other non-serializable types to strings
                        if hasattr(val, 'isoformat'):  # datetime-like objects
                            row_dict[col] = str(val)
                        elif isinstance(val, (bytes, bytearray)):  # binary data
                            row_dict[col] = "<binary>"
                        else:
                            row_dict[col] = val
                    sample_rows.append(row_dict)
                # logger.info(f"sample_rows: {sample_rows}")
                profile_text = self._build_table_profile_text(
                    schema_name, table_name, cols, sample_rows
                )

                fq_name = f"{schema_name}.{table_name}" if schema_name else table_name
                
                # Try two approaches: simple JSON first, then structured output if needed
                table_doc = None
                
                # Approach 1: Simple chat completion with JSON parsing (more reliable across models)
                try:
                    simple_messages = [
                        {
                            "role": "system", 
                            "content": "You are a data documentation assistant. Respond ONLY with valid JSON in this exact format:\n{\n  \"table_name\": \"exact_table_name\",\n  \"display_name\": \"Human Friendly Name\",\n  \"description\": \"Brief description of the table\",\n  \"columns\": {\"column_name\": \"description\", ...}\n}"
                        },
                        {
                            "role": "user",
                            "content": f"Document this table for finance analytics:\n{profile_text}\n\nTable name must be exactly: {fq_name}"
                        }
                    ]
                    
                    logger.info(f"Attempting JSON chat completion for {fq_name} using model: {llm.chat_model}")
                    response = llm.chat(messages=simple_messages)
                    response_text = response.choices[0].message.content.strip()
                    logger.info(f"Chat response for {fq_name}: {response_text[:200]}...")
                    
                    # Try to parse as JSON
                    import json
                    try:
                        doc_data = json.loads(response_text)
                        table_doc = TableDoc(
                            table_name=doc_data.get("table_name", fq_name),
                            display_name=doc_data.get("display_name", table_name.replace("_", " ").title()),
                            description=doc_data.get("description", "Generated table documentation"),
                            columns=doc_data.get("columns", {}),
                            synonyms=None
                        )
                        logger.info(f"Successfully parsed JSON documentation for {fq_name}")
                    except json.JSONDecodeError as json_err:
                        logger.warning(f"Failed to parse JSON response for {fq_name}: {json_err}")
                        raise ValueError("Could not parse JSON response")
                        
                except Exception as chat_error:
                    logger.info(f"JSON chat completion failed for {fq_name}: {chat_error}. Trying structured output...")
                    
                    # Approach 2: Structured output with tool calling (fallback)
                    try:
                        struct_messages = [
                            {
                                "role": "system",
                                "content": (
                                    "You are a data documentation assistant. Using the provided table profile, "
                                    "return a structured doc with ALL required fields: table_name, display_name, description, columns.\n"
                                    "Rules:\n"
                                    f"- table_name MUST be exactly '{fq_name}'.\n"
                                    "- display_name: a human-friendly Title Case name (no underscores).\n"
                                    "- description: 1-2 sentences summarizing what the table contains.\n"
                                    "- columns: include EVERY listed column (no new columns) with a brief meaning or the data type if unclear.\n"
                                    "Keep it concise and relevant to finance analytics."
                                ),
                            },
                            {
                                "role": "user",
                                "content": profile_text,
                            },
                        ]
                        
                        logger.info(f"Attempting structured output for {fq_name}")
                        table_doc = llm.get_structured_output(struct_messages, TableDoc())
                        logger.info(f"Structured output returned: table_name='{table_doc.table_name}', display_name='{table_doc.display_name}'")
                        # Validate that we got actual content
                        if not table_doc.table_name or not table_doc.display_name:
                            raise ValueError("Empty or incomplete structured output")
                        logger.info(f"Successfully generated structured documentation for {fq_name}")
                            
                    except Exception as struct_error:
                        logger.warning(f"Both JSON and structured output failed for {fq_name}. Using fallback.")
                        table_doc = None

                # Final fallback if both approaches failed
                if table_doc is None:
                    # Create a sensible fallback based on actual schema
                    column_descriptions = {}
                    for c in cols:
                        col_name = c["column_name"]
                        data_type = c.get("data_type", "")
                        # Simple heuristics for common financial columns
                        if "id" in col_name.lower():
                            column_descriptions[col_name] = f"Unique identifier ({data_type})"
                        elif "name" in col_name.lower() or "description" in col_name.lower():
                            column_descriptions[col_name] = f"Descriptive text ({data_type})"
                        elif "date" in col_name.lower() or "time" in col_name.lower():
                            column_descriptions[col_name] = f"Date/time value ({data_type})"
                        elif "amount" in col_name.lower() or "price" in col_name.lower() or "cost" in col_name.lower():
                            column_descriptions[col_name] = f"Monetary amount ({data_type})"
                        else:
                            column_descriptions[col_name] = data_type or "Data field"
                    
                    table_doc = TableDoc(
                        table_name=fq_name,
                        display_name=table_name.replace("_", " ").title(),
                        description=f"Financial data table containing {len(cols)} columns with sample records.",
                        columns=column_descriptions,
                        synonyms=None,
                    )

                text_for_embedding = "\n".join(
                    [
                        table_doc.display_name,
                        table_doc.description,
                        json.dumps(table_doc.columns, ensure_ascii=False),
                    ]
                )
                embedding = llm.generate_embedding(text_for_embedding)

                item = CatalogItem(
                    id=str(uuid4()),
                    schema_name=schema_name,
                    table_name=table_doc.table_name or (f"{schema_name}.{table_name}" if schema_name else table_name),
                    display_name=table_doc.display_name,
                    description=table_doc.description,
                    columns_json=json.dumps(table_doc.columns, ensure_ascii=False),
                    embedding_json=json.dumps(embedding),
                    created_at=datetime.utcnow().isoformat(),
                )
                # logger.info(f"item: {item}")
                items.append(item)
                indexed += 1
            except Exception as e:
                failures.append(f"{schema_name}.{table_name}: {e}")

        if items:
            self.vector_store.upsert(items)

        return {
            "tables_found": len(tables),
            "indexed": indexed,
            "failed": len(failures),
            "failures": failures,
        }


