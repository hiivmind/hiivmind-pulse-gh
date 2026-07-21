"""Explicit registration entry points for healthcheck adapters."""

from __future__ import annotations

from lib.pulse.scripts.adapters import claude_plugin, generic
from lib.pulse.scripts.check_adapters import AdapterRegistry


def register_universal_adapters(registry: AdapterRegistry) -> None:
    """Register universal adapters and their transitional aliases."""
    registry.register("generic.ci", generic.ci)
    registry.register("generic.documentation", generic.documentation)
    registry.register("generic.license", generic.license)
    registry.register("github.branch_protection", generic.branch_protection)
    registry.register("github.security_policy", generic.security_policy)

    registry.register("generic.docs", generic.documentation)
    registry.register("github.actions", generic.ci)


def register_claude_adapters(registry: AdapterRegistry) -> None:
    """Register Claude Code plugin adapters.

    These adapters are intentionally opt-in — they read overlay-scoped
    file contents that the neutral evidence snapshot does not carry.
    Callers wire them only when the Claude plugin overlay is enabled.
    """
    registry.register("claude.plugin_manifest", claude_plugin.plugin_manifest)
    registry.register("claude.skills", claude_plugin.skills)
    registry.register("claude.context", claude_plugin.context)


__all__ = ["register_universal_adapters", "register_claude_adapters"]
