"""Errors whose messages are safe and useful to show to the agent."""


class ToolInputError(Exception):
    """A problem the agent can read and recover from (bad path, no match, etc.)."""
