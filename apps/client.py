import argparse
import asyncio
import logging
import time
from asyncio import StreamReader, StreamWriter

import boto3
import websockets
from websockets import Subprotocol

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

BUFFER_SIZE = 65536


class MicrovmManager:
    def __init__(self, image_arn: str | None, region: str = "ap-northeast-1"):
        self.client = boto3.client("lambda-microvms", region_name=region)
        self.image_arn = image_arn
        self.microvm_id: str | None = None
        self.endpoint: str | None = None
        self.owner = False

    def start(self) -> str:
        assert isinstance(self.image_arn, str)

        response = self.client.run_microvm(
            imageIdentifier=self.image_arn,
            maximumDurationInSeconds=28800,
            idlePolicy={
                "autoResumeEnabled": True,
                "maxIdleDurationSeconds": 600,
                "suspendedDurationSeconds": 3600,
            },
        )
        self.microvm_id = response["microvmId"]
        self.endpoint = response["endpoint"]

        self.owner = True

        logger.info(f"MicroVM starting: {self.microvm_id}")
        logger.info("Waiting for MicroVM to be RUNNING...")

        while True:
            response = self.client.get_microvm(microvmIdentifier=self.microvm_id)
            state = response["state"]

            if state == "RUNNING":
                break
            if state in ("TERMINATING", "TERMINATED"):
                raise RuntimeError(f"MicroVM failed: {response.get('stateReason')}")
            time.sleep(5)

        logger.info(f"MicroVM is running: {self.endpoint}")

        return self.endpoint

    def create_token(self, port: int = 8080) -> str:
        assert isinstance(self.microvm_id, str)

        response = self.client.create_microvm_auth_token(
            microvmIdentifier=self.microvm_id,
            allowedPorts=[{"port": port}],
            expirationInMinutes=60,
        )
        return response["authToken"]["X-aws-proxy-auth"]

    def connect(self, microvm_id: str) -> str:
        self.microvm_id = microvm_id

        response = self.client.get_microvm(microvmIdentifier=microvm_id)
        state = response["state"]

        if state != "RUNNING":
            raise RuntimeError(f"MicroVM is not running: {state}")

        self.endpoint = response["endpoint"]
        logger.info(f"Connected to existing MicroVM: {self.endpoint}")

        return self.endpoint

    def stop(self):
        assert isinstance(self.microvm_id, str)

        if self.owner:
            self.client.terminate_microvm(microvmIdentifier=self.microvm_id)
            logger.info(f"MicroVM terminated: {self.microvm_id}")


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

                receiver = self.copy(ws.recv, writer.write)
                ws_to_tcp = asyncio.create_task(receiver)

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
    parser = argparse.ArgumentParser(description="Minecraft over Lambda MicroVMs")

    parser.add_argument("--image-arn", default=None)
    parser.add_argument("--microvm-id", default=None)
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--port", "-p", type=int, default=25565)
    parser.add_argument("--listen", "-l", default="127.0.0.1")

    args = parser.parse_args()

    if not args.image_arn and not args.microvm_id:
        parser.error("--image-arn or --microvm-id is required")

    manager = MicrovmManager(args.image_arn, args.region)

    if args.microvm_id:
        endpoint = manager.connect(args.microvm_id)
    else:
        endpoint = manager.start()

    token = manager.create_token(port=8080)

    ws_url = f"wss://{endpoint}"
    proxy = Proxy(
        port=args.port,
        addr=args.listen,
        url=ws_url,
        subprotocols=[
            Subprotocol("lambda-microvms"),
            Subprotocol(f"lambda-microvms.authentication.{token}"),
            Subprotocol("lambda-microvms.port.8080"),
        ],
    )

    try:
        asyncio.run(proxy.run())
    finally:
        manager.stop()


if __name__ == "__main__":
    main()
