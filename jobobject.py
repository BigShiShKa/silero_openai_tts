"""Compatibility imports; implementation lives in the installed app package."""
from app.client.jobobject import assign_pid_to_job, close_job, create_kill_on_close_job

__all__ = ["assign_pid_to_job", "close_job", "create_kill_on_close_job"]
