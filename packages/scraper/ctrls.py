import asyncio
import logging
import os

from packages.my_pyppeteer.ctrls import MyPyppeteer
from packages.core.utils.web_client import WebClient

from .utils import get_yaml

class CtrlBaseScraper:
    path_selectors = f'{os.path.dirname(os.path.realpath(__file__))}/storage/selectors.yaml'

    my_pyppeteer = None
    url_origin = None
    _selectors_ = None

    def __init__(self, browser_profile:str='Default', sem:int=2):
        self.browser_profile = browser_profile
        self.sem = asyncio.Semaphore(sem)

    @property
    def selectors(self):
        if not self._selectors_:
            self._selectors_ = get_yaml(self.path_selectors)
        return self._selectors_

    async def init_my_pyppeteer(self):
        """
        Inicializa el navegador web. Abre todas las pestañas que estaran
        disponibles durante el scraping.
        """
        if not self.my_pyppeteer:
            self.my_pyppeteer = MyPyppeteer(self.browser_profile)
            await self.my_pyppeteer.connect_browser()
            await self.my_pyppeteer.init_pool_pages(self.sem._value)

    async def run_on_page(self, url:str, callback, *args, **kwargs):
        """
        Espera que alla una pestaña disponible en el navegador.

        Navega a la url indicada y ejecuta el callback una vez la
        pagina cargue correctamente.

        Todas los callback deben tener como primer parametro
        el objecto page de pyppeteer.
        """
        await self.init_my_pyppeteer()
        async with self.sem:
            id_page, page = self.my_pyppeteer.get_page_pool()
            await page.goto(url)

            response = await callback(page, *args, **kwargs)
            self.my_pyppeteer.close_page_pool(id_page)
        return response

    async def get_data(self, page, *args, **kwargs)->tuple:
        selectors = self.selectors
        elements = dict()
        for item in selectors:
            if selectors[item]['multiple']:
                elements[item] = await self.my_pyppeteer.get_property_from_querySelectorAll(
                    selector=selectors[item]['css'],
                    attr=selectors[item]['pyppeteer'],
                    page=page
                )
            else:
                element = await self.my_pyppeteer.get_property_from_querySelector(
                    selector=selectors[item]['css'],
                    attr=selectors[item]['pyppeteer'],
                    page=page
                )
                elements[item] = element if element else ''

        bodyHTML = await page.evaluate("() => document.body.innerHTML")
        return elements, bodyHTML

    async def save_page(self, url):
        elements, bodyHTML = await self.run_on_page(url, self.get_data)
        with open('storage/example.html', 'w') as file:
            file.write(bodyHTML)
