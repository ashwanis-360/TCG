class PMBaseAdapter:
    """
    Abstract base class for all project management tool adapters.
    """

    def __init__(self, publisher):
        self.publisher = publisher  # Instance of TestCasePublisher

    def read(self):
        raise NotImplementedError("Each tool must implement this method")

    def write(self):
        raise NotImplementedError("Each tool must implement this method")

    def update(self):
        raise NotImplementedError("Each tool must implement this method")
