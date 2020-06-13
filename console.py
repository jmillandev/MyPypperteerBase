from cleo import Application
from packages.core.utils.app_loop import AppLoop
from packages.core.modules import ModuleManager
from packages.core.utils.logger import Logger

if __name__ == '__main__':
    application = Application("Go Shop Commands", 0.1, complete=True)
    AppLoop()
    ModuleManager().import_commands(application)
    Logger()
    application.run()