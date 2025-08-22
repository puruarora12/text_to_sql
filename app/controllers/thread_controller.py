from app.commands.threads.process_chat_message import ProcessChatMessageCommand
from app.commands.threads.conversation import ConversationCommand
from app.commands.threads.create_session import CreateSessionCommand

from app.controllers.controller import Controller


class ThreadController(Controller):
    """
    A controller for threads.
    """
    def process_chat_message(self, chat_messages: list) -> list:
        return self.executor.execute_write(ProcessChatMessageCommand(chat_messages))

    def conversation(self, session_id: str, messages: list):
        return self.executor.execute_read(ConversationCommand(session_id, messages))

    def create_session(self, session_name: str, user_type: str):
        return self.executor.execute_write(CreateSessionCommand(session_name, user_type))
