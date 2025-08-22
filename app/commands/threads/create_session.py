from typing import Dict

from app.core.commands import WriteCommand
from app.errors import ValidationException
from app.utils.formatters import get_timestamp

from langfuse.decorators import observe


# Session metadata store: session_id -> {user_type, created_at, session_name}
_SESSION_METADATA: Dict[str, Dict[str, str]] = {}


class CreateSessionCommand(WriteCommand):
	def __init__(self, session_name: str, user_type: str):
		self.session_name = session_name
		self.user_type = user_type

	def validate(self) -> None:
		if not self.session_name:
			raise ValidationException("session_name is required.")
		if not self.user_type:
			raise ValidationException("user_type is required.")
		if self.user_type not in ["user", "admin"]:
			raise ValidationException("user_type must be 'user' or 'admin'.")

	@observe()
	def execute(self) -> Dict[str, str]:
		self.validate()
		
		# Generate session ID
		import uuid
		session_id = str(uuid.uuid4())
		
		# Store session metadata
		_SESSION_METADATA[session_id] = {
			"session_name": self.session_name,
			"user_type": self.user_type,
			"created_at": get_timestamp(with_nanoseconds=True),
		}
		
		return {
			"session_id": session_id,
			"session_name": self.session_name,
			"user_type": self.user_type,
			"created_at": _SESSION_METADATA[session_id]["created_at"],
		}


def get_session_metadata(session_id: str) -> Dict[str, str]:
	"""Helper to retrieve session metadata."""
	return _SESSION_METADATA.get(session_id, {})
