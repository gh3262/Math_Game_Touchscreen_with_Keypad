class ReadFailedException(Exception):
    """
    Exception for read failures.
    """

    def __init__(self, message):
        super().__init__(message)