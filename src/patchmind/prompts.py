EXTRACTION_PROMPT = """Extract software-engineering entities and relationships.

Important entity types:
Repository, Branch, Commit, PullRequest, Issue, File, Symbol,
Component, Test, Failure, Attempt, Decision, Constraint and ReviewerConcern.

Important relationships:
MODIFIES, ATTEMPTED_TO_FIX, FAILED_BECAUSE, REJECTED_BECAUSE,
REVERTED_BECAUSE, RESOLVED_BY, PROTECTED_BY, DEPENDS_ON,
CONTRADICTS, SUPERSEDES, DISCUSSED_IN and AFFECTS.

Preserve commit hashes, file paths, test names, outcomes and evidence.
Do not interpret a failed or rejected attempt as an accepted recommendation.
"""
