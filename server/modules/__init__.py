"""
Module boundary registry — PathWise AI
Enforces the 14-module separation defined in SDD section 2.

Each module exposes only its public interface; cross-module calls
must go through these interfaces, not internal functions.

Used by tests/test_sdd_architecture.py to verify architectural conformance.
"""

MODULE_CONTRACTS: dict[str, list[str]] = {
    "TelemetryIngestionService": ["ingest_metrics", "get_current_state"],
    "LSTMPredictionEngine":      ["predict", "load_model", "get_health_score"],
    "HealthScoreCalculator":     ["compute_score", "is_below_threshold"],
    "AlertNotificationService":  ["send_alert", "suppress"],
    "TrafficSteeringController": ["execute_handoff", "preserve_session", "select_best_link"],
    "SDNControllerAdapter":      ["update_flow_table", "get_flow_state", "rollback_flow", "authenticate"],
    "DigitalTwinSandbox":        ["run_sandbox_validation"],
    "MininetTopologyBuilder":    ["build_topology", "apply_change", "detect_loops"],
    "BatfishPolicyAnalyzer":     ["analyze_compliance", "check_firewall", "generate_report"],
    "IBNPolicyTranslator":       ["parse_command", "to_yang_netconf", "validate"],
    "HealthScoreboard":          ["render_scores", "show_decision_reason", "export_report"],
    "AuthenticationService":     ["login", "validate_token", "lock_account"],
    "AuditLogger":               ["log_event", "query_logs", "verify_integrity"],
    "TimescaleDBRepository":     ["insert", "query_time_series", "compress"],
}
