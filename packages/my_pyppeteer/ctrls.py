from pyppeteer import launch, connect, errors
import asyncio
import re
import os
from packages.core.utils.singleton import SingletonClass
from sys import platform
from glob import glob
from pathlib import Path
import json
import yaml
import socket
import subprocess


class MyPyppeteer(metaclass=SingletonClass):
    """
    Clase para simular la navegacion de un usuario en un navegador
    """

    def __init__(self, profile='Default'):
        self.browser = None
        self.oppener = False
        self.max_opened_tabs = 50
        self._yaml = {}
        self.yaml_name = 'storage/pyppetter_browsers.yaml'
        self.profile = profile
        self.ws = None
        self.rotate_enabled = False
        self.TimeoutDefault = 0
        self.pool = {'availables':list()}
        self.flags = [
            '--window-size=1400,980',
            '--no-default-browser-check',
            '--process-per-tab',
            '--new-window',
            '--allow-running-insecure-content',
            '--silent-debugger-extension-api',

            '--disable-add-to-shelf',
            '--disable-background-downloads',
            '--disable-breakpad',  # Disable crashdump collection (reporting is already disabled in Chromium)
            '--disable-component-update',
            '--disable-datasaver-prompt',
            '--disable-desktop-notifications',
            '--disable-domain-reliability',
            '--disable-features=site-per-process',  # Disables OOPIF. https://www.chromium.org/Home/chromium-security/site-isolation
            '--disable-hang-monitor',
            '--disable-notifications',
            '--disable-sync',
            '--disable-translate-new-ux',  # No se si existe aun
            '--mute-audio',
            '--safebrowsing-disable-auto-update',
            '--disable-touch-adjustment',
            '--disable-speech-api',
            '--no-first-run',
            '--enable-automation',
        ]

    @property
    def yaml(self):
        if not self._yaml:
            if not os.path.exists(self.yaml_name):
                open(self.yaml_name, 'w').close()
            with open(self.yaml_name, 'r') as yamlfile:
                self._yaml = yaml.load(yamlfile)
                self._yaml = self._yaml if self._yaml else {}
        return self._yaml

    async def init_pool_pages(self, number_pages:int)->dict:
        if not self.browser:
            await self.connect_browser()
        # pages = await self.browser.pages()
        # pages[0].setDefaultNavigationTimeout(self.TimeoutDefault)
        # self.pool[0] = pages[0]
        # self.pool['availables'].append(0)
        for i in range(number_pages):
            self.pool[i] = await self.browser.newPage()
            self.pool[i].setDefaultNavigationTimeout(self.TimeoutDefault)
            self.pool['availables'].append(i)
        return self.pool

    async def change_page(self, page):
        for page_index in self.pool:
            if (page_index != 'availables') and (self.pool.get(page_index) == page):
                await page.close()
                self.pool[page_index] = await self.browser.newPage()
                self.pool[page_index].setDefaultNavigationTimeout(self.TimeoutDefault)
                return self.pool[page_index]

    def get_page_pool(self)->tuple:
        """
        Return:
            - id_page: El id de la pagina que se retorna(esta valor debe ser paso en el close_page_pool)
            - page: Una pagina activa del browser
        """
        page_id = self.pool['availables'].pop()
        return page_id, self.pool[page_id]

    def close_page_pool(self, page_id):
        self.pool['availables'].insert(0, page_id)

    def get_ws_profile(self):
        return self.yaml.get(self.profile)

    def set_ws_profile(self, ws=None):
        if not self.yaml:
            self.get_ws_profile()

        if self.yaml is not None:
            self.yaml[self.profile] = ws
            with open(self.yaml_name, 'w') as fp:
                yaml.dump(self.yaml, fp, default_flow_style=False)

    async def check_ws_opened(self):
        if not self.ws:
            return 0
        port = re.search(r'ws://(\d+\.\d+\.\d+\.\d+):(\d+)/', self.ws)
        ip = port.group(1)
        port = int(port.group(2))

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((ip, port))
        return result == 0

    async def connect_browser(self, ws=None, ask_input=True, **kwargs):
        if not self.browser:
            if ws:
                self.ws = ws
            if not self.ws:
                self.ws = self.get_ws_profile()
            if self.ws:
                if await self.check_ws_opened():
                    self.browser = await connect(browserWSEndpoint=self.ws)
                else:
                    self.set_ws_profile(None)
                    if ask_input:
                        msg = 'desea continuar en un explorador temporal? (se cerrara al terminar la ejecucion)'  # ' [Y/n] (tiene 15 seg para responder)'
                        print(msg)
                        resp = None
                        if resp and resp.lower() != 'y':
                            raise Exception(f'please, open pyppetter before, profile:{self.profile}, old_ws:{self.ws}, new_ws=None')

        if not self.browser:
            default_parrameters = {'headless': False, 'args': ['--no-sandbox'] + self.flags}
            default_parrameters.update(kwargs)
            kwargs = default_parrameters
            if self.profile:
                kwargs['userDataDir'] = await self.get_profile_dir()
            print(kwargs)
            self.browser = await launch(**kwargs)

        return await self.get_conenction(daemon=False)

    async def get_attribute(self, obj, attr, page=None):
        if not page:
            page = self.page
        if obj:
            return (await page.evaluate(f'(obj) => obj.getAttribute("{attr}")', obj))

    async def get_property(self, obj, attr, page=None):
        if not page:
            page = self.page
        if obj:
            return (await page.evaluate(f'(obj) => obj.{attr}', obj))

    async def set_property(self, obj, **kwargs):
        page = kwargs.pop('page', self.page)
        for attr, value in kwargs.items():
            await page.evaluate(f'(obj) => obj.{attr} = "{value}"', obj)

    async def get_property_from_querySelector(self, selector:str, attr:str, page=None):
        if not page:
            page = self.page
        return await page.evaluate('''() => {{
            obj = document.querySelector('{selector}')
            if (obj) {{
                return obj.{attr}
            }}
        }}'''.format(selector=selector,attr=attr))

    async def get_property_from_querySelectorAll(self, selector:str, attr:str, page=None):
        if not page:
            page = self.page
        return await page.evaluate('''() => {{
            obj = document.querySelectorAll('{selector}')
            return Array.from(obj).map(node => node.{attr})
        }}'''.format(selector=selector,attr=attr))

    async def count_pages(self):
        self.browser, self.page = await MyPyppeteer().connect_browser()
        print(f'{len(await self.browser.pages())}')

    async def get_conenction(self, daemon):
        if not self.ws:
            self.ws = self.browser.wsEndpoint

        if self.ws:
            self.set_ws_profile(self.ws)

        print(f'pyppeteer get_conenction, {self.profile} --> ws: {self.ws}')
        if daemon:
            input('Oprima (enter) para cerrar: ')
            await self.browser.close()
            return
        self.page = (await self.browser.pages())[0]
        return self.browser, self.page

    async def get_profile_dir(self):
        profile_dir = ''
        if platform == "linux" or platform == "linux2":  # linux
            paths = glob(f'{Path.home()}/.config/google-chrome/*/Preferences')
            paths += glob(f'{Path.home()}/.config/chromium/*/Preferences')
        elif platform == "darwin":  # mac
            paths = glob(f'{Path.home()}/Library/Application Support/Google/Chrome/*/Preferences')  # ruta
        elif platform == "win32":  # Windows...
            raise Exception('cuando alguien lo necesite, poner la ruta de chrome para windows, y probar')

        for path in paths:
            with open(path) as f:
                temp = json.load(f)
                if temp['profile']['name'] == self.profile:
                    profile_dir = '/'.join(path.split('/')[:-1])
                    break

        if not profile_dir and self.profile != "Default":
            raise Exception(f'Por favor crear perfil chrome con el nombre: "{self.profile}"')
        print('self.profile', self.profile)
        return profile_dir

    async def open_browser(self, daemon=True, **kwargs):
        # https://github.com/GoogleChrome/chrome-launcher/blob/master/docs/chrome-flags-for-tools.md

        extra_args = kwargs.pop('args', [])
        default_parrameters = {'headless': False, 'args': ['--no-sandbox', '--disable-setuid-sandbox'] + self.flags + extra_args}

        self.profile = kwargs.pop('profile_name', None)
        if self.profile:
            kwargs['userDataDir'] = await self.get_profile_dir()

        default_parrameters.update(kwargs)
        self.browser = await launch(**default_parrameters)
        self.oppener = True
        return await self.get_conenction(daemon)

    async def newPage(self, headless=False):
        for _ in range(10):
            count_tabs = len(await self.browser.pages())
            if count_tabs < self.max_opened_tabs:
                return await self.browser.newPage()
            print(f'pyppetter {count_tabs} de {self.max_opened_tabs} tabs abiertos,Esperando 5 segundos')
            await asyncio.sleep(5)
        raise Exception('despues de 50 segundos, No hay espacio para abrir un nuevo tab')

    async def click_and_wait(self, obj, **kwargs):
        ''' los kwargs son pra waitForNavigation'''

        page = kwargs.get('page')
        if not page:
            page = self.page
        try:
            return await asyncio.gather(page.waitForNavigation(**kwargs), self.click(obj, page=page))
        except errors.TimeoutError:
            print('ERROR, click_and_wait Timeout Exceeded')

    async def click(self, obj, **kwargs):
        page = kwargs.get('page')
        if not page:
            page = self.page
        return await page.evaluate('(obj) => obj.click()', obj)

    async def skip_error(self, function):
        try:
            return await function
        except errors.TimeoutError:
            print('skip_error, Timeout Exceeded')

    async def start_rotate_pages(self):
        self.rotate_enabled = True
        browser,_  = await self.connect_browser()
        for _ in range(1000):
            pages = await browser.pages()
            if not self.rotate_enabled:
                return
            for page in pages:
                if not page.isClosed():
                    try:
                        await page.bringToFront()
                        await asyncio.sleep(1)
                    except errors.NetworkError:
                        pass

    async def stop_rotate_pages(self):
        self.rotate_enabled = False
