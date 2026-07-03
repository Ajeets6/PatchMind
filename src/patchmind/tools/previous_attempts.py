async def run(service, repository_path: str, problem: str, file_path=None):
    return await service.find_previous_attempts(repository_path, problem, file_path)
