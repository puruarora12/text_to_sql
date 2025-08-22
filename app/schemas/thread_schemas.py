from app import ma


class ChatMessageSchema(ma.Schema):
    role = ma.String(required=True)
    content = ma.String(required=True)


class ChatMessagesSchema(ma.Schema):
    messages = ma.List(ma.Nested(ChatMessageSchema), required=True)


chat_messages_schema = ChatMessagesSchema()


class ConversationSchema(ma.Schema):
    session_id = ma.String(required=True)
    messages = ma.List(ma.Nested(ChatMessageSchema), required=True)


conversation_schema = ConversationSchema()


class CreateSessionSchema(ma.Schema):
    session_name = ma.String(required=True)
    user_type = ma.String(required=True, validate=lambda x: x in ["user", "admin"])


create_session_schema = CreateSessionSchema()