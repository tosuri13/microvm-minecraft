import argparse
import asyncio
import logging
from asyncio import StreamReader, StreamWriter

import websockets
from websockets import Subprotocol

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BUFFER_SIZE = 65536


class Proxy:
    def __init__(
        self,
        port: int,
        addr: str,
        url: str,
        subprotocols: list[Subprotocol] | None = None,
    ):
        self.port = port
        self.addr = addr
        self.url = url
        self.subprotocols = subprotocols

    async def copy(self, reader, writer):
        while True:
            data = await reader()
            if data == b"":
                break

            future = writer(data)
            if future:
                await future

    async def handle_client(
        self,
        reader: StreamReader,
        writer: StreamWriter,
    ):
        peer = writer.get_extra_info("peername")
        logger.info(f"{peer} connected")

        try:
            async with websockets.connect(
                self.url,
                subprotocols=self.subprotocols,
            ) as ws:
                logger.info(f"{peer} connected to {self.url}")

                sender = self.copy(lambda: reader.read(BUFFER_SIZE), ws.send)
                tcp_to_ws = asyncio.create_task(sender)

                reciever = self.copy(ws.recv, writer.write)
                ws_to_tcp = asyncio.create_task(reciever)

                done, pending = await asyncio.wait(
                    [tcp_to_ws, ws_to_tcp],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in done:
                    try:
                        await task
                    except Exception:
                        pass
                for task in pending:
                    task.cancel()

        except Exception:
            logger.exception(f"{peer} connection failed")

        writer.close()
        await writer.wait_closed()
        logger.info(f"{peer} closed")

    async def run(self):
        server = await asyncio.start_server(
            self.handle_client,
            self.addr,
            self.port,
        )

        logger.info(f"Listening on {self.addr}:{self.port}")
        logger.info(f"Forwarding to {self.url}")

        async with server:
            await server.serve_forever()


def main():
    parser = argparse.ArgumentParser(
        description="TCP to WebSocket proxy for Minecraft over Lambda MicroVMs",
    )

    parser.add_argument("url", help="WebSocket URL (ws://.. or wss://..)")
    parser.add_argument("--port", "-p", type=int, default=25565)
    parser.add_argument("--listen", "-l", default="127.0.0.1")
    parser.add_argument("--subproto", "-s", default="binary")

    args = parser.parse_args()

    subprotocols = [Subprotocol(args.subproto)] if args.subproto else None
    proxy = Proxy(args.port, args.listen, args.url, subprotocols)

    asyncio.run(proxy.run())


if __name__ == "__main__":
    main()
