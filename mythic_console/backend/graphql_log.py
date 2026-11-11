import re

from mythic import mythic
from mythic.mythic_classes import Mythic

from mythic_console.utils.logger import logger

_OPERATION_NAME_RE = re.compile(r"(query|mutation|subscription)\s+(\w+)")


async def logged_query(session: Mythic, query: str, variables: dict = None):
    """Issue a custom GraphQL query/mutation, logging the operation name and any failure."""
    match = _OPERATION_NAME_RE.search(query)
    op = match.group(2) if match else "anonymous"

    logger.debug(f"graphql {op}")
    try:
        return await mythic.execute_custom_query(mythic=session, query=query, variables=variables)
    except Exception as e:
        logger.warning(f"graphql {op} failed: {e}")
        raise
