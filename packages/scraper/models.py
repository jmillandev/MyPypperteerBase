# from packages.core.db import ConnectionsDB
# from packages.core.utils.config import Config

# class DemoModel():
#     """docstring for CtrlMod1"""

#     def __init__(self):
#         self.name_connection = 'db_scraper'

#     async def test(self):
#         query = "SELECT * FROM keywords_aws limit 10"
#         return await(await ConnectionsDB().get_connection("database")).select(query, 'all')

#     async def get_products_for_publish(self):
#         query = 'SELECT v.item_id AS item_id, c.mco AS category_mco\
#                 FROM variations_6pm AS v\
#                     INNER JOIN products_6pm AS p ON\
#                         p.productId = v.productId\
#                     INNER JOIN categories_6pm AS c ON\
#                         c.eng_name = p.category;'
#         return await(await ConnectionsDB().get_connection(self.name_connection)).select(query)

#     async def insert_brands(self, brands:list):
#         return await (
#             await ConnectionsDB().get_connection(self.name_connection)
#         ).insert(brands, 'brands_6pm', ['id'])

#     async def update_products(self, products:list):
#         fields = [f'{field}' for field in products[0].keys() if (
#             not field in ['productId']
#         )]
#         await (await ConnectionsDB().get_connection(self.name_connection)
#             ).insert(products, 'products_6pm', fields)