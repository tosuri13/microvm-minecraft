import asyncio
import logging
import os
import subprocess

import uvicorn
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import Response

MINECRAFT_PORT = int(os.getenv("MINECRAFT_PORT", "25565"))
RCON_PORT = int(os.getenv("RCON_PORT", "25575"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "microvm-minecraft")
HOOK_PORT = int(os.getenv("HOOK_PORT", "9000"))
HOOK_BASE = "/aws/lambda-microvms/runtime/v1"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

mc_process: subprocess.Popen | None = None


def exec_rcon(cmd: str):
    try:
        result = subprocess.run( 
            [
                "rcon-cli",
                "--host", "localhost",
                "--port", str(RCON_PORT),
                "--password", RCON_PASSWORD,
                cmd,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )  # fmt: skip
        logger.info(f"rcon '{cmd}': {result.stdout.strip()}")

        return result.stdout
    except Exception:
        logger.exception(f"rcon '{cmd}' failed")
        return None


def is_mc_server_ready() -> bool:
    result = subprocess.run(
        [
            "mc-monitor",
            "status",
            "--host", "localhost",
            "--port", str(MINECRAFT_PORT),
        ],
        capture_output=True,
    )  # fmt: skip

    return result.returncode == 0


router = APIRouter(prefix=HOOK_BASE)


@router.post("/ready")
async def ready():
    return Response(status_code=200)


@router.post("/run")
async def run(request: Request):
    global mc_process

    body = await request.body()
    logger.info(f"/run payload: {body.decode()}" if body else "/run")

    mc_process = subprocess.Popen(
        ["java", "-Xmx2G", "-jar", "server.jar", "--nogui"],
        cwd="/opt/minecraft",
    )

    for _ in range(60):
        if is_mc_server_ready():
            logger.info("Minecraft server is ready")
            break
        await asyncio.sleep(1)

    return Response(status_code=200)


@router.post("/suspend")
async def suspend():
    logger.info("Saving world before suspend")
    exec_rcon("save-all")

    return Response(status_code=200)


@router.post("/terminate")
async def terminate():
    logger.info("Stopping Minecraft server")
    exec_rcon("save-all")
    exec_rcon("stop")

    if mc_process:
        mc_process.wait(timeout=30)

    return Response(status_code=200)


@router.post("/resume")
async def resume():
    return Response(status_code=200)


@router.post("/validate")
async def validate():
    return Response(status_code=200)


app = FastAPI()
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=HOOK_PORT)
