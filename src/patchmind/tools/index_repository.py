async def run(service, repository_path: str, max_commits: int = 50, include_source: bool = True):
    return await service.index_repository(repository_path, max_commits, include_source)
