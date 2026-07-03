async def run(service, repository_path: str, task: str, file_paths=None, symbol=None, top_k=10):
    return await service.get_context(repository_path, task, file_paths, symbol, top_k)
