"""Explicit registration entry points for healthcheck adapters."""

from __future__ import annotations

from lib.pulse.scripts.adapters import generic
from lib.pulse.scripts.adapters import node_dependencies
from lib.pulse.scripts.adapters import python_dependencies
from lib.pulse.scripts.check_adapters import AdapterRegistry


def register_universal_adapters(registry: AdapterRegistry) -> None:
    """Register universal adapters and their transitional aliases."""
    registry.register("generic.ci", generic.ci)
    registry.register("generic.documentation", generic.documentation)
    registry.register("generic.license", generic.license)
    registry.register("github.branch_protection", generic.branch_protection)
    registry.register("github.security_policy", generic.security_policy)
    registry.register("python.dependencies", python_dependencies.evaluate_python)
    registry.register("node.dependencies", node_dependencies.evaluate_node)

    # Lazy: dependency_pipeline imports lib.pulse.scripts.adapters.{python,node}_
    # dependencies, so importing it at module level here would cycle back into
    # this very package's __init__. Deferring to call time breaks the cycle —
    # by then both submodules above are already fully imported.
    from lib.pulse.scripts.dependency_pipeline import (
        evaluate_fleet_dependency_coherence_placeholder,
    )

    registry.register(
        "fleet.dependencies.coherence", evaluate_fleet_dependency_coherence_placeholder
    )

    registry.register("generic.docs", generic.documentation)
    registry.register("github.actions", generic.ci)


def register_claude_adapters(registry: AdapterRegistry) -> None:
    """Register Claude Code plugin adapters.

    These adapters are intentionally opt-in — they read overlay-scoped
    file contents that the neutral evidence snapshot does not carry.
    Callers wire them only when the Claude plugin overlay is enabled.

    The overlay module is imported LAZILY here (not at module level) so that
    importing this package for the neutral ``register_universal_adapters``
    entry point never pulls the overlay — and its transitive dependencies —
    into the process. The dogfood-isolation test enforces this.
    """
    from lib.pulse.scripts.adapters import claude_plugin

    registry.register("claude.plugin_manifest", claude_plugin.plugin_manifest)
    registry.register("claude.skills", claude_plugin.skills)
    registry.register("claude.context", claude_plugin.context)


__all__ = ["register_universal_adapters", "register_claude_adapters"]
