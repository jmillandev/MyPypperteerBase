import asyncio
import logging
from packages.core.utils.singleton import SingletonClass


class AppLoop(metaclass=SingletonClass):
    event_loop = None

    def __init__(self):
        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())  # enable uvloop
            logging.getLogger('log_print').info('USANDO uvloop')
        except Exception as e:
            logging.getLogger('log_print').warn(f"Error ({e}) uvloop no soportado")
        self.event_loop = asyncio.get_event_loop()

    def __del__(self):
        if not self.event_loop.is_closed():
            print(dir(self.event_loop))
            self.event_loop.close()

    def get_loop(self):
        return self.event_loop