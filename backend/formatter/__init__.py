class FormatterNotAvailable(Exception):
    def __init__(self, command: str):
        """
        Error message when a formatter has not been implemented for a command

        :param command: command name
        """
        super().__init__(f"formatter not available for {command}")
