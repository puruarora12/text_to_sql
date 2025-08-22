from flask import Blueprint, request

from app.controllers.thread_controller import ThreadController
from app.decorators import handle_exceptions
from app.schemas.thread_schemas import chat_messages_schema, conversation_schema, create_session_schema
from app.utils.response import Response

thread_routes = Blueprint("thread_routes", __name__)
thread_controller = ThreadController()


@thread_routes.post("/chat")
@handle_exceptions
def chat():
    validated_request_data = chat_messages_schema.load(request.get_json())
    messages = thread_controller.process_chat_message(validated_request_data.get("messages"))
    return Response.make(messages, Response.HTTP_SUCCESS)


@thread_routes.post("/conversation")
@handle_exceptions
def conversation():
    data = conversation_schema.load(request.get_json())
    session_id = data.get("session_id")
    messages = data.get("messages", [])

    payload = thread_controller.conversation(session_id, messages)
    return Response.make(payload, Response.HTTP_SUCCESS)


@thread_routes.post("/sessions")
@handle_exceptions
def create_session():
    data = create_session_schema.load(request.get_json())
    session_name = data.get("session_name")
    user_type = data.get("user_type")

    payload = thread_controller.create_session(session_name, user_type)
    return Response.make(payload, Response.HTTP_SUCCESS)