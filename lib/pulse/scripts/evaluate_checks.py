#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Evaluate the mechanical healthcheck catalog from recorded API data.

Pure data comparison — no network. The caller (gh-healthcheck / a scheduler)
fetches the API responses listed below into --data-dir; this script evaluates
lib/references/healthcheck-checks.md's catalog and prints the per-repo block
of the `healthcheck` result kind (lib/patterns/headless-contract.md) as JSON.

LLM-judgment checks are out of scope here: none exist in the current catalog;
any added later are evaluated by the calling skill and flagged inferred: true.

Data-dir files (missing file => dependent check 'unknown', except where the
catalog defines absence as fail — e.g. protection.json absent means the API
returned 404 when repo.json is present):
  repo.json protection.json rulesets.json labels.json workflows.json
  releases.json tags.json root-contents.json github-contents.json

Usage:
  evaluate_checks.py --repo owner/name --data-dir DIR
                     [--relationships relationships.yaml]
                     [--dismissals healthcheck.yaml]

Scoring is weight-aware: pass=weight, warn=0.5*weight, fail=0. Unknown,
not_applicable, unsupported, and error are excluded from the score denominator.
Only unsupported weight is excluded from coverage_supported. Grade by score/total
fraction: A >= 0.90, B >= 0.72, C >= 0.54, D >= 0.36, F below.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
import json
from math import isfinite
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

BUG_LABELS = {"bug", "defect", "error", "incident"}
PRIORITY_HINTS = {"priority", "p0", "p1", "p2", "p3", "p4", "critical", "urgent"}
DEP_FILES = {"dependabot.yml", "dependabot.yaml", "renovate.json", ".renovaterc",
             ".renovaterc.json"}
RESULT_STATES = {
    "pass",
    "warn",
    "fail",
    "unknown",
    "not_applicable",
    "unsupported",
    "error",
}
LEGACY_SCORECARD = "github-governance-v1"


@dataclass(frozen=True)
class ScoreSummary:
    score: float
    total: float
    grade: str
    coverage_supported: float
    coverage_total: float


def score_checks(checks: dict[str, dict]) -> ScoreSummary:
    """Compute weighted health and adapter coverage from typed check results."""
    score = 0.0
    total = 0.0
    coverage_supported = 0.0
    coverage_total = 0.0
    for check_id, check in checks.items():
        status = check.get("status")
        if status not in RESULT_STATES:
            raise ValueError(f"unknown check state for {check_id}: {status}")
        weight = check.get("weight")
        if (
            isinstance(weight, bool)
            or not isinstance(weight, (int, float))
            or not isfinite(weight)
            or weight < 0
        ):
            raise ValueError(f"invalid check weight for {check_id}: {weight}")
        weight = float(weight)
        coverage_total += weight
        if status != "unsupported":
            coverage_supported += weight
        if status not in {"pass", "warn", "fail"}:
            continue
        total += weight
        score += {"pass": weight, "warn": weight * 0.5, "fail": 0.0}[status]
    score = round(score, 10)
    total = round(total, 10)
    coverage_supported = round(coverage_supported, 10)
    coverage_total = round(coverage_total, 10)
    return ScoreSummary(
        score,
        total,
        grade_for(score, total),
        coverage_supported,
        coverage_total,
    )


def aggregate_by_scorecard(
    repos: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, int | float | None]]:
    """Summarize repository scores without mixing scorecard populations."""
    repo_counts = Counter()
    percentages: dict[str, list[float]] = defaultdict(list)
    for repo in repos:
        scorecard = repo["scorecard"]
        if not isinstance(scorecard, str):
            raise ValueError("repository scorecard must be a string")
        repo_counts[scorecard] += 1
        total = repo["total"]
        score = repo["score"]
        if not isinstance(total, (int, float)) or not isinstance(score, (int, float)):
            raise ValueError("repository score and total must be numbers")
        if total:
            percentages[scorecard].append(score / total * 100)
    return {
        scorecard: {
            "repos": count,
            "repos_scored": len(percentages[scorecard]),
            "average_percent": (
                round(sum(percentages[scorecard]) / len(percentages[scorecard]), 2)
                if percentages[scorecard]
                else None
            ),
        }
        for scorecard, count in sorted(repo_counts.items())
    }


def fleet_coverage(
    repos: Sequence[Mapping[str, object]],
) -> dict[str, int | dict[str, int]]:
    """Summarize emitted check coverage and unsupported adapter debt."""
    unsupported = Counter()
    checks_total = 0
    checks_supported = 0
    for repo in repos:
        checks = repo["checks"]
        if not isinstance(checks, Mapping):
            raise ValueError("repository checks must be a mapping")
        for check in checks.values():
            if not isinstance(check, Mapping):
                raise ValueError("check must be a mapping")
            checks_total += 1
            if check.get("status") == "unsupported":
                adapter = check.get("adapter")
                if not isinstance(adapter, str):
                    raise ValueError("check adapter must be a string")
                unsupported[adapter] += 1
            else:
                checks_supported += 1
    return {
        "checks_total": checks_total,
        "checks_supported": checks_supported,
        "unsupported_by_adapter": dict(sorted(unsupported.items())),
    }


def load(data_dir: Path, name: str):
    f = data_dir / name
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        return None


def names(listing) -> set[str]:
    return {e.get("name", "") for e in (listing or [])}


def check_branch_protection(d):
    if d["repo"] is None:
        return "unknown", "repo metadata unavailable"
    prot, rules = d["protection"], d["rulesets"]
    active_rulesets = any(r.get("enforcement") == "active" for r in (rules or []))
    if prot is None and not active_rulesets:
        return "fail", "No protection rules and no active rulesets on default branch"
    if prot is not None:
        admins = (prot.get("enforce_admins") or {}).get("enabled", False)
        reviews = (prot.get("required_pull_request_reviews") or {})
        count = reviews.get("required_approving_review_count", 0)
        if not admins or count < 1:
            return "warn", f"Protection exists but enforce_admins: {str(admins).lower()}, required reviews: {count}"
        return "pass", f"Protected ({count} required review(s), enforce_admins)"
    return "pass", "Active ruleset on default branch"


def check_project_linkage(d, repo):
    rel = d["relationships"]
    if rel is None:
        return "unknown", "no relationships data provided"
    links = rel.get("project_repo_links") or []
    linked = [link for link in links if repo in (link.get("repos") or [])]
    if linked:
        return "pass", f"Linked to {len(linked)} project(s)"
    return "fail", "Repo not linked to any project"


def check_issue_triage(d):
    if d["labels"] is None:
        return "unknown", "labels unavailable"
    labels = {label.get("name", "").lower() for label in d["labels"]}
    has_bug = bool(labels & BUG_LABELS)
    has_prio = any(any(h in lbl for h in PRIORITY_HINTS) for lbl in labels)
    if has_bug and has_prio:
        return "pass", "Bug-type and priority labels present"
    if has_bug or has_prio:
        return "warn", "Has bug-type or priority labels, not both"
    return "fail", "Missing both bug-type and priority labels"


def check_ci_cd(d):
    if d["workflows"] is None:
        return "unknown", "workflows unavailable"
    n = d["workflows"].get("total_count", 0)
    return ("pass", f"{n} workflow(s) configured") if n > 0 else ("fail", "No workflow files found")


def check_releases(d):
    if d["releases"] is None and d["tags"] is None:
        return "unknown", "releases/tags unavailable"
    if d["releases"]:
        return "pass", f"{len(d['releases'])} release(s)"
    if d["tags"]:
        return "warn", "Tags exist but no formal releases"
    return "fail", "No releases or tags"


def check_documentation(d):
    root = d["root"]
    if root is None:
        return "unknown", "contents unavailable"
    root_names = names(root)
    has_readme = "README.md" in root_names
    has_extra = "CONTRIBUTING.md" in root_names or "docs" in root_names
    if has_readme and has_extra:
        return "pass", "README ✓, docs/ or CONTRIBUTING ✓"
    if has_readme:
        return "warn", "README exists but no CONTRIBUTING.md and no docs/"
    return "fail", "No README.md"


def check_codeowners(d):
    if d["root"] is None and d["github"] is None:
        return "unknown", "contents unavailable"
    for where, listing in (("CODEOWNERS", d["root"]), (".github/CODEOWNERS", d["github"])):
        if "CODEOWNERS" in names(listing):
            return "pass", f"Found at {where}"
    return "fail", "No CODEOWNERS file found"


def check_security_policy(d):
    if d["root"] is None and d["github"] is None:
        return "unknown", "contents unavailable"
    if "SECURITY.md" in names(d["root"]) or "SECURITY.md" in names(d["github"]):
        return "pass", "SECURITY.md present"
    return "fail", "No SECURITY.md found"


def check_license(d):
    if d["repo"] is None:
        return "unknown", "repo metadata unavailable"
    lic = d["repo"].get("license")
    if lic:
        return "pass", str(lic.get("spdx_id") or lic.get("name") or "present")
    if any(n.startswith("LICENSE") for n in names(d["root"])):
        return "pass", "LICENSE file present"
    return "fail", "No LICENSE file found"


def check_dependency_management(d):
    if d["root"] is None and d["github"] is None:
        return "unknown", "contents unavailable"
    found = (names(d["root"]) | names(d["github"])) & DEP_FILES
    if found:
        return "pass", f"Configured: {sorted(found)[0]}"
    return "fail", "No dependency management tool configured"


def check_secrets_scanning(d):
    if d["repo"] is None:
        return "unknown", "repo metadata unavailable"
    saa = d["repo"].get("security_and_analysis") or {}
    scanning = (saa.get("secret_scanning") or {}).get("status")
    push = (saa.get("secret_scanning_push_protection") or {}).get("status")
    if scanning == "enabled" and push == "enabled":
        return "pass", "Secret scanning + push protection enabled"
    if scanning == "enabled":
        return "warn", "Secret scanning enabled but push protection disabled"
    if scanning is None:
        return "unknown", "secret scanning status not visible (needs admin)"
    return "fail", "Secret scanning not enabled"


def grade_for(score: float, total: float) -> str:
    if total == 0:
        return "F"
    frac = score / total
    for g, floor_ in (("A", 0.90), ("B", 0.72), ("C", 0.54), ("D", 0.36)):
        if frac >= floor_:
            return g
    return "F"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--relationships", default="")
    ap.add_argument("--dismissals", default="")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    d = {
        "repo": load(data_dir, "repo.json"),
        "protection": load(data_dir, "protection.json"),
        "rulesets": load(data_dir, "rulesets.json"),
        "labels": load(data_dir, "labels.json"),
        "workflows": load(data_dir, "workflows.json"),
        "releases": load(data_dir, "releases.json"),
        "tags": load(data_dir, "tags.json"),
        "root": load(data_dir, "root-contents.json"),
        "github": load(data_dir, "github-contents.json"),
        "relationships": (yaml.safe_load(Path(args.relationships).read_text())
                          if args.relationships and Path(args.relationships).exists()
                          else None),
    }

    dismissed: dict = {}
    if args.dismissals and Path(args.dismissals).exists():
        hc = yaml.safe_load(Path(args.dismissals).read_text()) or {}
        for scope in ((hc.get("dismissals") or {}).get(args.repo, {}),
                      (hc.get("dismissals") or {}).get(args.repo.split("/")[-1], {})):
            dismissed.update(scope or {})

    evaluators = {
        "branch_protection": lambda: check_branch_protection(d),
        "project_linkage": lambda: check_project_linkage(d, args.repo),
        "issue_triage": lambda: check_issue_triage(d),
        "ci_cd": lambda: check_ci_cd(d),
        "releases": lambda: check_releases(d),
        "documentation": lambda: check_documentation(d),
        "codeowners": lambda: check_codeowners(d),
        "security_policy": lambda: check_security_policy(d),
        "license": lambda: check_license(d),
        "dependency_management": lambda: check_dependency_management(d),
        "secrets_scanning": lambda: check_secrets_scanning(d),
    }

    checks: dict = {}
    for cid, fn in evaluators.items():
        adapter = f"github.{cid}"
        if cid in dismissed:
            reason = (dismissed[cid] or {}).get("reason", "")
            checks[cid] = {
                "check_id": cid,
                "adapter": adapter,
                "weight": 1,
                "status": "not_applicable",
                "detail": f"Dismissed: {reason}",
                "data": {"dismissed": True, "reason": reason},
            }
            continue
        status, detail = fn()
        checks[cid] = {
            "check_id": cid,
            "adapter": adapter,
            "weight": 1,
            "status": status,
            "detail": detail,
            "data": {},
        }

    summary = score_checks(checks)
    print(json.dumps({
        "repo": args.repo,
        "scorecard": LEGACY_SCORECARD,
        "score": summary.score,
        "total": summary.total,
        "grade": summary.grade,
        "coverage_supported": summary.coverage_supported,
        "coverage_total": summary.coverage_total,
        "checks": checks,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
