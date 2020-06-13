from .commands import AllCommands
from cleo import Command


class setup():
    """setup de My Pyppeteer"""

    def router(self, app):
        pass

    def commands(self, app):
        all_commands = [v for v in AllCommands.__dict__.values() if isinstance(v, type) and issubclass(v, Command)]
        for command in all_commands:
            app.add(command())
