from flask import Blueprint, request

from app.decorators import handle_exceptions
from app.services.catalog.table_catalog_service import TableCatalogService
from app.utils.response import Response


admin_routes = Blueprint("admin_routes", __name__)


@admin_routes.post("/scan_db")
@handle_exceptions
def scan_db():
    body = request.get_json(silent=True) or {}
    limit_rows = int(body.get("limit_rows", 5))
    schema = body.get("schema")

    service = TableCatalogService()
    result = service.scan_and_index(limit_rows=limit_rows, schema_filter=schema)

    return Response.make(result, Response.HTTP_SUCCESS)


