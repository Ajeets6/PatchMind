async def run(service, repository_path: str, session_id: str, summary: str):
    return await service.finalize_session(repository_path, session_id, summary)
