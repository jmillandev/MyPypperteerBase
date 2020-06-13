import asyncio
import logging
import os

from packages.my_pyppeteer.ctrls import MyPyppeteer
from packages.core.utils.web_client import WebClient


class CtrlBaseScraper:
    path_selectors = f'{os.path.dirname(os.path.realpath(__file__))}/storage/selectors.yaml'

    my_pyppeteer = None
    url_origin = None

    def __init__(self, browser_profile:str='Default', sem:int=2):
        self.browser_profile = browser_profile
        self.sem = asyncio.Semaphore(sem)

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
    
    async def get_page_body(self, page):
        return await page.evaluate("() => document.body.innerHTML")

    async def save_page(self, url):
        bodyHTML = await self.run_on_page(url, self.get_page_body)
        with open('storage/example.html', 'w') as file:
            file.write(bodyHTML)
