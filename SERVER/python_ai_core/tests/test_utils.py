import logging
class syntheticMsg:
    def __init__(self, data, subject="incident.reanalyze"):
        self.data = data
        self.subject = subject
    async def ack(self):
        logging.getLogger(__name__).debug('_ = None suppressed')
    async def nak(self):
        logging.getLogger(__name__).debug('_ = None suppressed')
