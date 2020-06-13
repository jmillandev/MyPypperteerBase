from packages.core.utils.singleton import SingletonClass as Singleton
from packages.core.utils.app_loop import  AppLoop

import itertools
import json
import asyncio
import re
import subprocess
import aiohttp
import logging
import sys
import concurrent
from random import randint

class WebClient(metaclass=Singleton):
    def __init__(self, *args, **kwargs):
        self.all_sessions = None
        self.lock = asyncio.Lock()
        # faster
        # http://azenv.net/
        # http://httpheader.net/azenv.php
        # http://proxyjudge.us/azenv.php
        # http://www.proxyfire.net/fastenv

        # medium
        # http://httpbin.org/get?show_env
        # http://www.sbjudge3.com/azenv.php
        # https://httpbin.org/get?show_env

        # > 0.2 sec
        # http://www.proxy-listen.de/azenv.php
        # https://www.proxy-listen.de/azenv.php
        # http://www.sbjudge2.com/azenv.php
        # http://www.proxyjudge.info/azenv.php

        # ?
        # https://api.ipify.org?format=json
        # http://ip-api.com/json
        # http://httpbin.org/ip

        self.url_judges = ("http://azenv.net/", "http://httpheader.net/azenv.php")

    async def internet_check(self, session, skip=False):
        if skip:
            public_ip = session._connector._local_addr[0]
            self.ip_publics.append(public_ip)
            return session
        for url_judge in self.url_judges:
            async with session.get(url_judge, timeout=20) as resp:
                if resp:
                    resp = await resp.text()
                    public_ip = re.findall(r"\d+\.\d+\.\d+\.\d+", resp)

                    if public_ip not in self.ip_publics:
                        self.ip_publics.append(public_ip)
                        return session
            logging.getLogger('log_print').error(
                f"internet_check error con: url_judge: {url_judge}, {session._connector._local_addr[0]}"
            )

        await session.close()
        return

    async def starts(self):
        try:
            cmd = r"ip -o -4 addr show|grep ' en\| eth\| wl'|awk '{print $4}'|cut -d/ -f1"  # deja solo las redes : "enp|eth" sin vpn sin docker
            ps = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            ips = ps.communicate()[0].decode().strip().split()
        except Exception as e:  # si es windows
            logging.getLogger('log_print').error(f"Error, {e}, es windows?")
            ips = ["0.0.0.0"]
        if not ips:
            raise Exception("no hay ips de salida disponibles")

        self.sessions = []
        self.ip_publics = []
        coros = []
        for ip in ips:
            conn = aiohttp.connector.TCPConnector(
                local_addr=(ip, 0), limit=300, loop=AppLoop().get_loop()
            )
            session = AutoRetrySession(
                connector=conn,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible MSIE 9.0 Windows NT 6.1 Trident/5.0)"
                },
            )
            coros.append(self.internet_check(session, skip=len(ips) > 10))

        self.sessions = filter(None, await asyncio.gather(*coros))
        if len(self.ip_publics) > 0:
            logging.getLogger("log_print").info(
                f"Usando {len(self.ip_publics)} Ips_rotativas"
            )
        else:
            raise Exception(
                f"Error, no hay ips disponibles con internet testeado con: {self.url_judges}"
            )
            exit()

        self.all_sessions = self.get_all_sessions()

    async def do_request(
            self,
            uri:str,
            rq_type="get",
            payload=dict(),
            params=None,
            return_data="json",
            headers=dict(),
            cookies=dict(),
            **kwargs,
        ):
            if payload:
                payload = json.dumps(payload)

            max_reintents = 30
            i = 0
            while i < max_reintents:  # max_reintents por si no recibe un Json
                i += 1
                async with (await self.get_session()).__getattribute__(rq_type)(
                    uri,
                    data=payload,
                    params=params,
                    headers=headers,
                    verify_ssl=False,
                    cookies=cookies
                ) as resp:
                    if not resp:
                        logging.getLogger("log_print").error(
                            f"not resp {rq_type} {uri} {payload} {params}"
                        )
                        return
                    try:
                        res_json = {}
                        if return_data == "json":
                            if resp.content_type == "text/html":
                                logging.getLogger("log_print").error(
                                    f"{rq_type} {resp.status} {uri} \
    error jot json response: {await resp.text()} "
                                )
                                return

                            res_json = await resp.json()
                            if isinstance(res_json, (list, dict)):
                                final_res = res_json
                        elif return_data == "text":
                            res_text = await resp.text()
                            if res_text:
                                final_res = res_text
                        elif return_data is None:
                            final_res = None

                        if resp.status in (200, 201, 206):
                            if isinstance(final_res, list) and any(
                                1 for i in final_res if i.get("code") == 500 or i.get("status") == 500
                            ):
                                logging.getLogger("log_print").debug(
                                    f"{rq_type}, {resp.status}, {resp.url}, some one with code:500"
                                )
                                continue
                            return final_res
                        elif resp.status in (403,):  # 403 = Forbidden (meli day limit)
                            return final_res
                        elif resp.status in (
                            429,
                            500,
                            501,
                            502,
                            409,
                            504,
                        ):  # 504=not found(temporaly), 409 =optimistic locking, 429 = toomany request
                            if 0 < i < 5:
                                logging.getLogger("log_print").debug(
                                    f"{rq_type} {resp.status} retrying No-{i} , too quikly? {0.2 * i}"
                                )
                            elif 5 < i:
                                logging.getLogger("log_print").info(
                                    f"{rq_type} {resp.status} retrying No-{i} , too quikly? {0.2 * i}"
                                )
                            await asyncio.sleep(0.2 * i)
                            continue
                        # elif resp.status == 401:  # expired_token
                        #     print(
                        #         f"{rq_type} status 401, expired_token, forcing to refresh, {resp.url}"
                        #     )
                        #     token = await self.get_token(force=True)
                        #     params["access_token"] = token
                        #     max_reintents /= 3
                        #     continue
                        elif resp.status in (404, 400, 401) and isinstance(res_json, dict):
                            logging.getLogger("log_print").debug(
                                f"{rq_type}, {resp.status}, {resp.url}, {res_json.get('message')}, {res_json.get('cause')}"
                            )
                            return final_res
                        else:
                            if res_json:
                                logging.getLogger("log_print").info(
                                    f"{rq_type}, {resp.status}, {resp.url}, -{await resp.text()}-"
                                )
                            return final_res
                    except Exception as e:
                        logging.getLogger("log").error(
                            f"Error on {rq_type} return_data:{return_data} {uri}, {e}"
                        )
                        await asyncio.sleep(0.5)
                        continue

    async def get(
        self, uri, payload={}, params=None, return_data="json", headers={}, **kwargs
    ):
        return await self.do_request(
            rq_type="get",
            uri=uri,
            payload=payload,
            params=params,
            return_data=return_data,
            headers=headers,
            **kwargs,
        )

    async def post(
        self, uri, payload={}, params=None, return_data="json", headers={}, **kwargs
    ):
        return await self.do_request(
            rq_type="post",
            uri=uri,
            payload=payload,
            params=params,
            return_data=return_data,
            headers=headers,
            **kwargs,
        )

    async def put(
        self, uri, payload={}, params=None, return_data="json", headers={}, **kwargs
    ):
        return await self.do_request(
            rq_type="put",
            uri=uri,
            payload=payload,
            params=params,
            return_data=return_data,
            headers=headers,
            **kwargs,
        )

    async def delete(
        self, uri, payload={}, params=None, return_data="json", headers={}, **kwargs
    ):
        return await self.do_request(
            rq_type="delete",
            uri=uri,
            payload=payload,
            params=params,
            return_data=return_data,
            headers=headers,
            **kwargs,
        )

    async def get_session(self):
        with await self.lock:
            if not self.all_sessions:
                await self.starts()
        return self.session

    @property
    def session(self):
        return next(self.all_sessions)

    def get_all_sessions(self):
        positions = itertools.cycle(self.sessions)
        for session in itertools.islice(
            positions, randint(0, len(self.ip_publics)), None
        ):
            yield session

async def retry_if_disconect(function, *args, **kwargs):
    for i in range(1, 16):
        try:
            return await function(*args, **kwargs)
        except asyncio.TimeoutError:  # do not retry if timeout
            error = f"{function.__name__}:error Timeout = {args}"
            logging.getLogger("log_print").debug(error)
            return
        except (
            aiohttp.client_exceptions.ClientConnectorError,
            aiohttp.client_exceptions.ServerDisconnectedError,
            aiohttp.client_exceptions.ClientResponseError,
            concurrent.futures.CancelledError,
        ):
            local_ip = function.__self__._connector._local_addr[0]
            logging.getLogger("log_print").warning(
                f"{function.__name__}: AutoRetrySession sleep({round(0.1 * i, 2)}),{sys.exc_info()[0]}, {args} {local_ip}"
            )
            await asyncio.sleep(round(0.1 * i, 2))
        except aiohttp.client_exceptions.InvalidURL:
            error = f"error InvalidURL = {args}"
            raise Exception(error)
        except Exception as e:
            logging.getLogger('log_print').error(f"Unexpected error ({e}):", sys.exc_info()[0])

class GetRetry:
    def __init__(self, function, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.resp = None
        self.function = function

    async def __aenter__(self):
        self.resp = await retry_if_disconect(self.function, *self.args, **self.kwargs)
        return self.resp

    async def __aexit__(self, exc_type, exc, tb):
        if self.resp:
            await self.resp.release()

class AutoRetrySession(aiohttp.ClientSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get(self, *args, **kwargs):
        return GetRetry(super().get, *args, **kwargs)

    def post(self, *args, **kwargs):
        return GetRetry(super().post, *args, **kwargs)

    def put(self, *args, **kwargs):
        return GetRetry(super().put, *args, **kwargs)

    def delete(self, *args, **kwargs):
        return GetRetry(super().delete, *args, **kwargs)