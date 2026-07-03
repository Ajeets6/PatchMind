import argparse
import asyncio

from patchmind.memory.cognee_store import CogneeMemoryStore
from patchmind.service import PatchMindService


async def run(repository: str) -> None:
    service = PatchMindService(CogneeMemoryStore())
    print(await service.index_repository(repository))
    print(await service.get_context(repository, "Why does the session store use its current lock?"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("repository")
    asyncio.run(run(parser.parse_args().repository))
