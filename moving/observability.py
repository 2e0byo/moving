import os

import logfire


def register_logfire() -> bool:
    if token := os.getenv("LOGFIRE_TOKEN"):
        logfire.configure(token=token)
        logfire.instrument_httpx()
        return True
    else:
        return False
