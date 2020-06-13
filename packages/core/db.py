from packages.core.utils.app_loop import AppLoop
from packages.core.utils.singleton import SingletonClass
from packages.core.utils.mysql import UnicodeFilter
from packages.core.utils.config import Config

from pymysql.err import (
    OperationalError,
    InternalError,
)  # InternalError = cualquier error interno de mysql (incluso error de sintaxis)
from unicodedata import normalize
import aiomysql
import asyncio
import itertools
import logging
import sys
from datetime import datetime


class CursorIterator:
    def __init__(self, cur, step=1000):
        self.cur = cur
        self.step = step
        self.iter = None
        self.res_gen = None
        self.final_res = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        while True:
            if self.iter is None:
                self.iter = await self.cur.fetchmany(self.step)
                if self.iter == [] or self.iter == ():
                    break
                self.res_gen = self.my_gen()
            res = next(self.res_gen, None)
            if res:
                return res
        raise StopAsyncIteration

    def __len__(self):
        return self.cur.rowcount

    def my_gen(self):
        for i in self.iter:
            yield i
        self.iter = None


class DataBase:
    """docstring for DataBase"""

    def __init__(self, name_connection):
        self.cursor = self.pool = None
        self.name_connection = name_connection
        self.conn_config = None

    async def mysql_pool_create(self, conn_config):
        parammeters = (
            "host",
            "port",
            "db",
            "user",
            "password",
        )
        self.conn_config = {param: conn_config[param] for param in parammeters}
        try:
            self.pool = await aiomysql.create_pool(
                cursorclass=aiomysql.cursors.DictCursor,
                maxsize=15,
                autocommit=True,
                loop=AppLoop().get_loop(),
                charset="utf8mb4",
                **self.conn_config,
            )
        except Exception:
            self.conn_config.pop("password")
            logging.getLogger("log").error(f"Error in create_pool {self.conn_config}")
            raise
        return self

    def get_current_pool(self):
        return self.pool

    async def select(
        self, sqls, ret_type="all", cursorclass="DictCursor", step=2, **kw
    ):
        if cursorclass == "DictCursor":
            cursorclass = aiomysql.cursors.DictCursor
        elif cursorclass == "Cursor":
            cursorclass = aiomysql.cursors.Cursor
        pool = self.get_current_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(cursorclass) as cur:
                if isinstance(sqls, str):
                    sqls = [sqls]
                for sql in sqls:
                    await self.core_execute(conn, cur, sql, **kw)

                if ret_type == "all":
                    return await cur.fetchall()
                elif ret_type == "async_all":
                    return CursorIterator(cur, step)
                elif ret_type == "one":
                    return await cur.fetchone()
                elif ret_type == "count":
                    return cur.rowcount
                else:
                    return cur

    async def core_execute(self, conn, cur, sql, **kw):
        max_retry = 5
        for i in range(max_retry):
            try:
                await cur.execute(sql, kw.get("args", None))
                break
            except (OperationalError, RuntimeError) as e:
                logging.getLogger("log").error(
                    f"{e}, se perdio la conexion con el servidor?? {sql}"
                )
                ConnectionsDB().connections.pop(self.name_connection, None)
                logging.getLogger("log").error(
                    f"Se borra conexion {self.name_connection} para nuevo intento en 10 seg, intento ({i}/{max_retry})"
                )
                await asyncio.sleep(10)
                await ConnectionsDB().get_connection(self.name_connection)
            except Exception as e:
                logging.getLogger("log").error(
                    f'Mysql {sys.exc_info()[0]} {e} {kw}\n {self.conn_config["host"]} sql: {sql}'
                )
                break

        return cur

    async def get_conn(self):
        self.connection = await self.pool.acquire()
        return self.connection

    async def execute(self, sql, txt_cursorclass="DictCursor", **kw):
        if txt_cursorclass == "DictCursor":
            cursorclass = aiomysql.cursors.DictCursor
        elif txt_cursorclass == "Cursor":
            cursorclass = aiomysql.cursors.Cursor

        pool = self.get_current_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(cursorclass) as cur:
                await self.core_execute(conn, cur, sql, **kw)
                return cur

    async def mogrify(self, sql, args):
        pool = self.get_current_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                return cur.mogrify(sql, args)

    async def mogrify_many(self, args):
        pool = self.get_current_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                if not args:
                    return
                str_vars = "(" + ",".join(itertools.repeat("%s", len(args[0]))) + ")"
                texto = ",".join(itertools.repeat(str_vars, len(args)))
                all_args = [i for i in itertools.chain(*args)]
                try:
                    res = cur.mogrify(f"{texto}", all_args)
                    res = UnicodeFilter(res)  # remove \uFFFF chars
                except Exception as e:
                    print(args)
                    print(len(args[0]), args[0])
                    print(texto, args, len(args))
                    raise

                return res

    async def executemany(self, sql, args, txt_cursorclass="DictCursor"):
        if txt_cursorclass == "DictCursor":
            cursorclass = aiomysql.cursors.DictCursor
        elif txt_cursorclass == "Cursor":
            cursorclass = aiomysql.cursors.Cursor
        pool = self.get_current_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(cursorclass) as cur:
                await cur.executemany(sql, args)
                return cur

    async def execute_big_insert(self, arr_values, query_schema):
        res = None
        arr_final_query = await self.prepare_big_insert(arr_values, query_schema)
        for final_query in arr_final_query:
            # breakpoint()
            res = await self.execute(
                final_query
            )  # todo agregar a execute_core sending all params
        if res:
            return res

    async def prepare_big_insert(self, args, query_schema, values_format="({})"):
        arr_values = []
        split_n_from = 0
        min_start_len = 10000
        max_string_size = 30000000
        if len(args) > 0 and not isinstance(args[0], (list, tuple)):
            args = [[i] for i in args]
        for split_n_to in range(
            min_start_len, len(args) + min_start_len + 1, min_start_len
        ):  # para empezar de a min_start_len
            if (
                args[split_n_from:split_n_to]
                and (
                    sum(
                        map(
                            lambda x: sum(
                                len(i) if type(i) == str else len(str(i)) for i in x
                            ),
                            args[split_n_from:split_n_to],
                        )
                    )
                    > max_string_size
                )
                or split_n_to >= len(args)
            ):
                args_spl = args[split_n_from:split_n_to]
                split_n_from = split_n_to
                args_list = []
                for x in args_spl:
                    vals = ",".join(["%s"] * len(x))
                    args_list.append(await self.mogrify(f"({vals})", x))
                values = ",".join(args_list)
                if values:
                    arr_values.append(values)
        return [query_schema.format(values_str) for values_str in arr_values]
    
    async def insert(self, items:list, table:str, updates:list):
        """
        Inserta valores en una tabla de la base de datos.
        Parameters:
        items: Una lista con los registros a insertar
        table: El nombre de la tabla donde se insertaran los registros
        updates: Una lista con el nombre de los campos a actualizar(Si pasas solo un key este registro se ignora.)
        """
        fields = ', '.join([f"`{field}`" for field in items[0].keys()])
        query = f"INSERT INTO {table} ({fields}) VALUES"
        query = query + ' {} ON DUPLICATE KEY UPDATE'
        for column in updates:
            query +=  f' `{column}` = VALUES({column}),'
        query = f'{query[:-1]};'
        values = [tuple(item.values()) for item in items]
        return await (
            await ConnectionsDB().get_connection("db_scraper")
        ).execute_big_insert(values, query)

    async def close(self):
        print("close pool")
        pool = self.get_current_pool()
        if pool:
            pool.close()
            print("closed pool")


class ConnectionsDB(metaclass=SingletonClass):
    """docstring for ConnectionsDB"""

    def __init__(self):
        self.lock = asyncio.Lock()
        self.connections = {}

    async def get_connection(self, name_connection):
        conn_config = Config().config_yaml()["db"]["connections"][name_connection]
        async with self.lock:
            if not self.connections.get(name_connection):
                self.connections[name_connection] = await DataBase(
                    name_connection
                ).mysql_pool_create(conn_config)
        return self.connections[name_connection]

    async def closeAll(self):
        for key in self.connections:
            print("close db... ", key)
            await self.connections[key].close()