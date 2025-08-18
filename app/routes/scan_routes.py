from flask import Blueprint, request

from app.controllers.scan_controller import ScanController
from app.decorators import handle_exceptions
from app.utils.response import Response

scan_routes = Blueprint("scan_routes", __name__)
scan_controller = ScanController()


@scan_routes.get("/tables")
@handle_exceptions
def get_tables():
    tables = scan_controller.get_tables()
    return Response.make(tables, Response.HTTP_SUCCESS)