from langfuse.decorators import observe
from vaul import tool_call
from typing import Dict, Any, List

from app import logger
from app.services.vector_store.vector_store_service import VectorStoreService
from app.services.datastore.duckdb_datastore import DuckDBDatastore

import re


@tool_call
@observe
def db_schema_vector_search(natural_language_query: str, n_results: int = 5) -> Dict[str, str]:
	"""
	Fetch concise database context for SQL generation using vector search plus a compact DB schema summary.

	Returns a dictionary with:
	- context_text: lines like "[schema.table] - description"
	- schema_text: a compact list of tables and columns
	"""
	# Vector search for table descriptions
	context_text = ""
	try:
		vector_store = VectorStoreService(collection_name="dbschema", index_name="dbschema")
		results: List[Dict[str, Any]] = vector_store.search(natural_language_query, n_results=n_results)
		logger.info(f"Vector results: {results}")
		lines: List[str] = []
		for item in results[:n_results]:
			if not isinstance(item, dict):
				continue
			metadata = item.get("metadata", {}) or {}
			schema_name = metadata.get("schema_name")
			doc = (item.get("document") or item.get("chunk_text") or "")
			if not doc:
				continue
			# Extract table name from text body: "Table: <name>"
			tmatch = re.search(r"^Table:\s*(.+)$", doc, re.MULTILINE)
			table_from_text = tmatch.group(1).strip() if tmatch else None
			if not table_from_text:
				table_from_text = metadata.get("table_name")
			if not table_from_text:
				continue
			header = f"[{schema_name + '.' if schema_name else ''}{table_from_text}]"
			# Extract description line
			dmatch = re.search(r"^Description:\s*(.+)$", doc, re.MULTILINE)
			if dmatch:
				description = dmatch.group(1).strip()
			else:
				first_line = next((ln.strip() for ln in doc.splitlines() if ln.strip() and not ln.strip().lower().startswith("table:")), "")
				description = first_line[:240]
			lines.append(f"{header} - {description}")
		context_text = "\n".join(lines)
	except Exception as e:
		logger.error(f"db_schema_vector_search: vector search failed: {e}")
		context_text = ""

	# Compact DB schema summary
	schema_text = ""
	try:
		datastore = DuckDBDatastore(database="app/data/data.db")
		tables = datastore.get_list_of_tables()
		lines = []
		for t in tables[:8]:
			tbl = t.get("table_name", "")
			sch = t.get("table_schema", "")
			columns = datastore.get_list_of_columns(tbl, sch)
			col_parts = [
				f"{c.get('column_name')} {c.get('data_type')}" + (" NOT NULL" if c.get("is_nullable") == "NO" else "")
				for c in columns[:10]
			]
			header = f"[{sch + '.' if sch else ''}{tbl}]"
			lines.append(header + ("\n  - " + "\n  - ".join(col_parts) if col_parts else ""))
		schema_text = "\n\n".join(lines)
	except Exception as e:
		logger.error(f"db_schema_vector_search: schema summary failed: {e}")
		schema_text = ""

	return {"context_text": context_text, "schema_text": schema_text}


