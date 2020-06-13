import glob
import importlib
from .utils.singleton import SingletonClass
import aiohttp_jinja2
import jinja2
import logging


class ModuleManager(metaclass=SingletonClass):
    """docstring for setup_modules"""

    def __init__(self):
        self.app = {}
        self.modules_path = []
        self.modules = {}
        self.inited = False

    def set_app(self, app):
        if not self.inited:
            self.app = app

    def load_module(self, mod_path):
        path = mod_path.replace("/", ".").replace('\\', ".").replace(".py", "")
        if path in self.modules_path:
            return True
        mod = getattr(importlib.import_module(path), "setup")()
        mod.path = path
        if hasattr(mod, "name"):
            self.modules[mod.name] = mod
        else:
            self.modules[path] = mod

        self.modules_path.append(path)
        return True

    def load_modules(self):
        mods = glob.glob("packages/**/setup.py")
        for mod in mods:
            self.load_module(mod)

    def import_routes(self, app):
        self.load_modules()
        print(f"importing routers: ({self.modules.keys()})")
        for name in self.modules:
            mod = self.modules[name]
            if hasattr(mod, "router"):
                mod.router(app)

    def import_templates(self, app):
        logging.getLogger('log_print').debug('skip import_templates')
        return
        self.load_modules()
        templates = {}
        print(f"load templates: ({self.modules.keys()})")
        for name in self.modules:
            mod = self.modules[name]
            templates[name] = jinja2.PackageLoader(mod.path.replace(".setup", ""), "templates")
        loader = jinja2.PrefixLoader(templates)
        aiohttp_jinja2.setup(app, loader=loader)

    def import_commands(self, app):
        self.load_modules()
        for name in self.modules:
            mod = self.modules[name]
            if hasattr(mod, "commands"):
                mod.commands(app)

    def get_modules(self):
        return self.modules

    def get_config(self, name_module):
        if name_module in self.modules:
            if hasattr(self.modules[name_module], "config"):
                return self.modules[name_module].config


def config(name_module):
    manager = ModuleManager()
    return manager.get_config(name_module)
