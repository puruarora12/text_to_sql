import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import duckdb


@dataclass
class CatalogItem:
    id: str
    schema_name: Optional[str]
    table_name: str
    display_name: str
    description: str
    columns_json: str
    embedding_json: str
    created_at: str


class DuckDBVectorStore:
    """A lightweight vector store backed by DuckDB for catalog items."""

    def __init__(self, db_path: str = "app/data/data.db") -> None:
        self.connection = duckdb.connect(database=db_path)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS table_catalog (
              id TEXT PRIMARY KEY,
              schema_name TEXT,
              table_name TEXT NOT NULL,
              display_name TEXT NOT NULL,
              description TEXT NOT NULL,
              columns_json TEXT NOT NULL,
              embedding_json TEXT NOT NULL,
              created_at TIMESTAMP NOT NULL
            )
            """
        )

    def upsert(self, items: List[CatalogItem]) -> None:
        if not items:
            return
        data = [
            (
                it.id,
                it.schema_name,
                it.table_name,
                it.display_name,
                it.description,
                it.columns_json,
                it.embedding_json,
                it.created_at,
            )
            for it in items
        ]
        self.connection.executemany(
            """
            INSERT INTO table_catalog (id, schema_name, table_name, display_name, description, columns_json, embedding_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
              schema_name=excluded.schema_name,
              table_name=excluded.table_name,
              display_name=excluded.display_name,
              description=excluded.description,
              columns_json=excluded.columns_json,
              embedding_json=excluded.embedding_json,
              created_at=excluded.created_at
            """,
            data,
        )

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def query(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id, schema_name, table_name, display_name, description, columns_json, embedding_json FROM table_catalog"
        ).fetchall()

        scored: List[Tuple[float, Dict[str, Any]]] = []
        for row in rows:
            embedding = json.loads(row[6]) if row[6] else []
            score = self._cosine_similarity(query_embedding, embedding)
            scored.append(
                (
                    score,
                    {
                        "id": row[0],
                        "schema_name": row[1],
                        "table_name": row[2],
                        "display_name": row[3],
                        "description": row[4],
                        "columns": json.loads(row[5]) if row[5] else {},
                        "score": score,
                    },
                )
            )

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]


