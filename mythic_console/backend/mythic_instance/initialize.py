# from logger import logger
#
# from backend.user.user import User
# from backend.operation.operation import Operation
#
#
# async def initialize_user(instance, username: str) -> User:
#     logger.debug("initializing user")
#     user = User(instance, username=username)
#     await user.query()
#     return user
#
#
# async def initialize_operation(instance, operation_id: int) -> Operation:
#     logger.debug("initializing operation")
#     operation = Operation(instance, operation_id=operation_id)
#     await operation.query()
#     return operation
