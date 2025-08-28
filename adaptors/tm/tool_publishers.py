
class BaseToolPublisher:
    def __init__(self, publisher):
        self.publisher = publisher  # Instance of TestCasePublisher

    def publish(self):
        raise NotImplementedError("Each tool must implement this method")

