"""Pure, repository-type-neutral healthcheck adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from lib.pulse.scripts.check_adapters import CheckContext


F0_FILES_REF = "f0:files"


def _result(
    status: str,
    detail: str,
    *,
    paths: Sequence[str] = (),
    refs: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "status": status,
        "detail": detail,
        "data": {
            "evidence": {
                "paths": list(paths),
                "refs": list(refs),
            }
        },
    }


def _files(context: CheckContext) -> tuple[str, ...] | None:
    value = context.evidence.get("files")
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return None
    if not all(isinstance(path, str) for path in value):
        return None
    return tuple(value)


def ci(context: CheckContext) -> dict[str, Any]:
    """Evaluate whether the F0 manifest contains GitHub Actions workflows."""
    files = _files(context)
    if files is None:
        return _result("unknown", "workflows unavailable")

    workflows = sorted(
        path
        for path in files
        if path.startswith(".github/workflows/")
        and path.lower().endswith((".yml", ".yaml"))
    )
    if workflows:
        return _result(
            "pass",
            f"{len(workflows)} workflow(s) configured",
            paths=workflows,
            refs=(F0_FILES_REF,),
        )
    return _result("fail", "No workflow files found", refs=(F0_FILES_REF,))


def documentation(context: CheckContext) -> dict[str, Any]:
    """Evaluate root documentation from the normalized F0 manifest."""
    files = _files(context)
    if files is None:
        return _result("unknown", "contents unavailable")

    has_readme = "README.md" in files
    if "CONTRIBUTING.md" in files:
        extra = "CONTRIBUTING.md"
    elif "docs" in files:
        extra = "docs"
    else:
        extra = next(
            (path for path in sorted(files) if path.startswith("docs/")), None
        )
    if has_readme and extra:
        return _result(
            "pass",
            "README ✓, docs/ or CONTRIBUTING ✓",
            paths=("README.md", extra),
            refs=(F0_FILES_REF,),
        )
    if has_readme:
        return _result(
            "warn",
            "README exists but no CONTRIBUTING.md and no docs/",
            paths=("README.md",),
            refs=(F0_FILES_REF,),
        )
    return _result("fail", "No README.md", refs=(F0_FILES_REF,))


def license(context: CheckContext) -> dict[str, Any]:
    """Evaluate API license metadata with an F0 root-file fallback."""
    files = _files(context)
    github = context.evidence.get("github")
    repo = github.get("repo") if isinstance(github, Mapping) else None
    license_metadata = repo.get("license") if isinstance(repo, Mapping) else None
    if isinstance(license_metadata, Mapping) and license_metadata:
        label = (
            license_metadata.get("spdx_id")
            or license_metadata.get("name")
            or "present"
        )
        return _result("pass", str(label), refs=("github:repo",))

    if files is None:
        refs = ("github:repo",) if isinstance(repo, Mapping) else ()
        return _result("unknown", "repo metadata unavailable", refs=refs)

    license_paths = sorted(
        path for path in files if "/" not in path and path.startswith("LICENSE")
    )
    refs = [F0_FILES_REF]
    if isinstance(repo, Mapping):
        refs.insert(0, "github:repo")
    if license_paths:
        return _result(
            "pass", "LICENSE file present", paths=(license_paths[0],), refs=refs
        )
    return _result("fail", "No LICENSE file found", refs=refs)


def branch_protection(context: CheckContext) -> dict[str, Any]:
    """Evaluate recorded default-branch protection and ruleset facts."""
    github = context.evidence.get("github")
    if not isinstance(github, Mapping):
        return _result("unknown", "branch protection unavailable")

    required = ("repo", "protection", "rulesets")
    if any(key not in github for key in required):
        refs = tuple(f"github:{key}" for key in required if key in github)
        return _result("unknown", "branch protection unavailable", refs=refs)

    refs = tuple(f"github:{key}" for key in required)
    repo = github["repo"]
    if not isinstance(repo, Mapping):
        return _result("unknown", "repo metadata unavailable", refs=refs)

    protection = github["protection"]
    rulesets = github["rulesets"]
    active_rulesets = isinstance(rulesets, Sequence) and any(
        isinstance(rule, Mapping) and rule.get("enforcement") == "active"
        for rule in rulesets
    )
    if protection is None and not active_rulesets:
        return _result(
            "fail",
            "No protection rules and no active rulesets on default branch",
            refs=refs,
        )
    if isinstance(protection, Mapping):
        admins_value = protection.get("enforce_admins") or {}
        reviews_value = protection.get("required_pull_request_reviews") or {}
        admins = (
            admins_value.get("enabled", False)
            if isinstance(admins_value, Mapping)
            else False
        )
        count = (
            reviews_value.get("required_approving_review_count", 0)
            if isinstance(reviews_value, Mapping)
            else 0
        )
        if not admins or not isinstance(count, int) or count < 1:
            return _result(
                "warn",
                "Protection exists but enforce_admins: "
                f"{str(admins).lower()}, required reviews: {count}",
                refs=refs,
            )
        return _result(
            "pass",
            f"Protected ({count} required review(s), enforce_admins)",
            refs=refs,
        )
    if active_rulesets:
        return _result(
            "pass", "Active ruleset on default branch", refs=refs
        )
    return _result("unknown", "branch protection unavailable", refs=refs)


def security_policy(context: CheckContext) -> dict[str, Any]:
    """Evaluate a root or GitHub metadata-directory security policy."""
    files = _files(context)
    if files is None:
        return _result("unknown", "contents unavailable")

    policy = next(
        (path for path in ("SECURITY.md", ".github/SECURITY.md") if path in files),
        None,
    )
    if policy:
        return _result(
            "pass",
            "SECURITY.md present",
            paths=(policy,),
            refs=(F0_FILES_REF,),
        )
    return _result("fail", "No SECURITY.md found", refs=(F0_FILES_REF,))
