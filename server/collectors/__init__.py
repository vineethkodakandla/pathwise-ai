"""
Real-time network telemetry collectors for PathWise AI.

Each collector talks to actual hardware/APIs to gather live metrics.
All collectors implement the same interface: async collect() → TelemetryPoint.
"""
