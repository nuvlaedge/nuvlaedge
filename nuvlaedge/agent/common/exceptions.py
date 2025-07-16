class ActionTimeoutError(Exception):
    def __init__(self, name: str, period: int, original_exception: Exception = None):
        self.name = name
        self.period = period
        self.original_exception = original_exception
        super().__init__(f"Timeout occurred for '{name}' after {period} seconds.")
