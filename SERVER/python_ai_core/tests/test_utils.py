class syntheticMsg:
    def __init__(self, data, subject="incident.reanalyze"):
        self.data = data
        self.subject = subject
    async def ack(self):
        import logging; logging.getLogger(__name__).debug('_ = None suppressed')
    async def nak(self):
        import logging; logging.getLogger(__name__).debug('_ = None suppressed')
