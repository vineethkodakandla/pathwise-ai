"""
Verify that the modules defined in SDD section 2 exist and expose their
public interfaces. Closes Gap 9 (SDD architectural conformance).
"""

import importlib

import pytest


# Map of (module path -> required public symbols).
# These are the SDD §2 modules that ARE implemented in the consolidated
# `server/` backend (the rest are wired into main.py / state.py inline).
REQUIRED_MODULES = {
    "server.sdn_adapter":  ["SDNControllerAdapter", "get_adapter"],
    "server.sandbox":      ["run_sandbox_validation", "validate_steering"],
    "server.ibn_engine":   ["deploy_intent", "parse_intent", "generate_yang_config"],
    "server.routing":      ["execute_hitless_handoff", "rollback_handoff",
                            "build_flow_body"],
    "server.modules":      ["MODULE_CONTRACTS"],
}


@pytest.mark.parametrize("module_path,symbols", list(REQUIRED_MODULES.items()))
def test_module_exists_and_exports(module_path, symbols):
    """Each SDD module must be importable and expose its public interface."""
    try:
        mod = importlib.import_module(module_path)
    except ImportError as e:
        pytest.fail(f"Module {module_path} missing: {e}")

    for symbol in symbols:
        assert hasattr(mod, symbol), \
            f"{module_path} must export '{symbol}' per SDD section 2"


def test_module_contracts_registry_populated():
    """The MODULE_CONTRACTS registry must list all 14 SDD modules."""
    from server.modules import MODULE_CONTRACTS
    assert len(MODULE_CONTRACTS) == 14, \
        f"SDD section 2 defines 14 modules, found {len(MODULE_CONTRACTS)}"
