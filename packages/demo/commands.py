from cleo import Command
from packages.core.utils.app_loop import AppLoop


class AllCommands:
    pass

    # class Test(Command):
    #     """
    #     Test

    #     scraper:amazon_scan_product
    #     {--sku= : sku}
    #     {--country= : country}
    #     """

    #     def handle(self):
    #         sku = self.option('sku')
    #         country = self.option('country') if self.option('country') else 'usa'

    #         AppLoop().get_loop().run_until_complete(())

    #     async def handleAsync(self):
    #         await update_all_images_ml()
