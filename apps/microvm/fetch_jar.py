import argparse
import json
from pathlib import Path
from urllib.request import urlopen, urlretrieve

MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"


def fetch(version: str, output: Path):
    output.mkdir(parents=True, exist_ok=True)

    manifest = json.load(urlopen(MANIFEST_URL))
    versions = manifest["versions"]
    version_url = next(v["url"] for v in versions if v["id"] == version)

    meta = json.load(urlopen(version_url))
    server_url = meta["downloads"]["server"]["url"]

    jar_path = output / "server.jar"
    urlretrieve(server_url, output / "server.jar")
    print(f"Downloaded Minecraft {version} to {jar_path}")

    (output / "eula.txt").write_text("eula=true\n")

    properties = output / "server.properties"
    if not properties.exists():
        properties.write_text(
            "enable-rcon=true\n"
            "rcon.port=25575\n"
            "rcon.password=microvm-minecraft\n"
        )  # fmt: skip


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=Path("/opt/minecraft"))

    args = parser.parse_args()

    fetch(args.version, args.output)
