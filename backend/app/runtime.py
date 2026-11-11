"""Shared in-process coordination for API requests."""

import asyncio

chat_request_tasks: set[asyncio.Task] = set()
chat_session_locks: dict[str, asyncio.Lock] = {}
data_mutation_condition = asyncio.Condition()
delete_all_lock = asyncio.Lock()
active_mutation_requests = 0
deleting_all_data = False
