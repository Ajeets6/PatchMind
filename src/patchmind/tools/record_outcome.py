async def run(service, repository_path: str, session_id: str, task: str, approach: str, outcome: str, evidence: str, affected_files: list[str], tests=None):
    return await service.record_outcome(repository_path, session_id, task, approach, outcome, evidence, affected_files, tests)
