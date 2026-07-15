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


def _files_complete(context: CheckContext) -> bool:
    """Legacy absence and observational F0 snapshots are both incomplete."""
    return context.evidence.get("files_complete") is True


def _evidence_gap(
    detail: str,
    *,
    paths: Sequence[str] = (),
    refs: Sequence[str] = (F0_FILES_REF,),
) -> dict[str, Any]:
    return _result(
        "unknown", f"Evidence gap: {detail}", paths=paths, refs=refs
    )


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
    if _files_complete(context):
        return _result("fail", "No workflow files found", refs=(F0_FILES_REF,))
    return _evidence_gap("workflow absence is not established")


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
        if not _files_complete(context):
            return _evidence_gap(
                "additional documentation absence is not established",
                paths=("README.md",),
            )
        return _result(
            "warn",
            "README exists but no CONTRIBUTING.md and no docs/",
            paths=("README.md",),
            refs=(F0_FILES_REF,),
        )
    if _files_complete(context):
        return _result("fail", "No README.md", refs=(F0_FILES_REF,))
    return _evidence_gap("README absence is not established")


def license(context: CheckContext) -> dict[str, Any]:
    """Evaluate API license metadata with an F0 root-file fallback."""
    files = _files(context)
    github = context.evidence.get("github")
    repo = github.get("repo") if isinstance(github, Mapping) else None
    license_metadata = repo.get("license") if isinstance(repo, Mapping) else None
    if isinstance(license_metadata, Mapping):
        spdx_id = license_metadata.get("spdx_id")
        if (
            isinstance(spdx_id, str)
            and spdx_id
            and spdx_id != "NOASSERTION"
        ):
            return _result("pass", spdx_id, refs=("github:repo",))

    license_paths = sorted(
        path
        for path in files or ()
        if "/" not in path and path.startswith("LICENSE")
    )
    if license_paths:
        return _result(
            "pass",
            "LICENSE file present",
            paths=(license_paths[0],),
            refs=(F0_FILES_REF,),
        )
    if isinstance(repo, Mapping) and "license" in repo and license_metadata is None:
        return _result(
            "fail", "GitHub reports no recognized license", refs=("github:repo",)
        )
    if files is None:
        refs = ("github:repo",) if isinstance(repo, Mapping) else ()
        return _evidence_gap("license metadata and files are unavailable", refs=refs)
    if _files_complete(context):
        refs = [F0_FILES_REF]
        if isinstance(repo, Mapping):
            refs.insert(0, "github:repo")
        return _result("fail", "No LICENSE file found", refs=refs)
    refs = [F0_FILES_REF]
    if isinstance(repo, Mapping):
        refs.insert(0, "github:repo")
    return _evidence_gap("license absence is not established", refs=refs)


def _default_branch_ruleset_match(
    rule: Mapping[str, Any], default_branch: Any
) -> bool | None:
    """Return whether an active branch ruleset demonstrably targets the default."""
    conditions = rule.get("conditions")
    if not isinstance(conditions, Mapping):
        return None
    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, Mapping):
        return None
    include = ref_name.get("include")
    exclude = ref_name.get("exclude")
    if (
        isinstance(include, (str, bytes))
        or not isinstance(include, Sequence)
        or isinstance(exclude, (str, bytes))
        or not isinstance(exclude, Sequence)
        or not all(isinstance(ref, str) for ref in (*include, *exclude))
    ):
        return None

    explicit_ref = (
        f"refs/heads/{default_branch}"
        if isinstance(default_branch, str) and default_branch
        else None
    )
    default_tokens = {"~ALL", "~DEFAULT_BRANCH"}
    if explicit_ref is not None:
        default_tokens.add(explicit_ref)
    included = any(ref in default_tokens for ref in include)
    excluded = any(ref in default_tokens for ref in exclude)
    return included and not excluded


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
    if isinstance(rulesets, (str, bytes)) or not isinstance(rulesets, Sequence):
        return _result("unknown", "ruleset targeting unavailable", refs=refs)
    active_branch_rulesets = [
        rule
        for rule in rulesets
        if isinstance(rule, Mapping)
        and rule.get("enforcement") == "active"
        and rule.get("target") == "branch"
    ]
    matches = [
        _default_branch_ruleset_match(rule, repo.get("default_branch"))
        for rule in active_branch_rulesets
    ]
    if any(match is True for match in matches):
        return _result(
            "pass", "Active ruleset on default branch", refs=refs
        )
    if any(match is None for match in matches):
        return _result(
            "unknown", "active branch ruleset targeting unavailable", refs=refs
        )
    if protection is None:
        return _result(
            "fail",
            "No protection rules and no active rulesets on default branch",
            refs=refs,
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
    if _files_complete(context):
        return _result("fail", "No SECURITY.md found", refs=(F0_FILES_REF,))
    return _evidence_gap("SECURITY.md absence is not established")
