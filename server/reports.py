"""
Report generation — PDF and CSV export of health scores, steering events, and predictions.

Implements Req-Func-Sw-21: Exportable performance reports.
"""

from __future__ import annotations
import csv
import io
import time
from typing import Optional

from server.state import state
from server import audit


# ── CSV Generation ─────────────────────────────────────────────

def generate_health_scores_csv() -> str:
    """Export current health scores and predictions for all links."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["link_id", "health_score", "confidence", "latency_forecast_avg",
                      "jitter_forecast_avg", "packet_loss_forecast_avg", "timestamp"])

    for link_id, pred in state.predictions.items():
        if pred:
            lat_avg = sum(pred.latency_forecast) / len(pred.latency_forecast) if pred.latency_forecast else 0
            jit_avg = sum(pred.jitter_forecast) / len(pred.jitter_forecast) if pred.jitter_forecast else 0
            pkt_avg = sum(pred.packet_loss_forecast) / len(pred.packet_loss_forecast) if pred.packet_loss_forecast else 0
            writer.writerow([
                link_id, round(pred.health_score, 1), round(pred.confidence, 3),
                round(lat_avg, 2), round(jit_avg, 2), round(pkt_avg, 4),
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(pred.timestamp)),
            ])

    return output.getvalue()


def generate_steering_events_csv(limit: int = 200) -> str:
    """Export steering event history."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "timestamp", "action", "source_link", "target_link",
                      "traffic_classes", "confidence", "reason", "status", "lstm_enabled"])

    for evt in list(state.steering_history)[:limit]:
        writer.writerow([
            evt.id,
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(evt.timestamp)),
            evt.action, evt.source_link, evt.target_link,
            evt.traffic_classes, round(evt.confidence, 2),
            evt.reason, evt.status, evt.lstm_enabled,
        ])

    return output.getvalue()


def generate_audit_log_csv(limit: int = 500) -> str:
    """Export audit log entries."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "event_time", "event_type", "actor", "link_id",
                      "health_score", "confidence", "validation_result", "details", "checksum"])

    entries = audit.get_all_entries_raw()[-limit:]
    for e in entries:
        writer.writerow([
            e.id,
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(e.event_time)),
            e.event_type, e.actor, e.link_id,
            round(e.health_score, 1) if e.health_score else "",
            round(e.confidence, 3) if e.confidence else "",
            e.validation_result or "", e.details or "",
            e.checksum[:16] + "...",
        ])

    return output.getvalue()


# ── PDF Generation ─────────────────────────────────────────────

def generate_health_scores_pdf() -> bytes:
    """Generate PDF report of health scores."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "PathWise AI - Health Scores Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(8)

    # Table header
    pdf.set_font("Helvetica", "B", 9)
    col_widths = [40, 25, 25, 30, 25, 30]
    headers = ["Link ID", "Health", "Confidence", "Lat Avg (ms)", "Jit Avg", "Loss Avg (%)"]
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, align="C")
    pdf.ln()

    # Table data
    pdf.set_font("Helvetica", "", 8)
    for link_id, pred in state.predictions.items():
        if pred:
            lat_avg = sum(pred.latency_forecast) / max(len(pred.latency_forecast), 1)
            jit_avg = sum(pred.jitter_forecast) / max(len(pred.jitter_forecast), 1)
            pkt_avg = sum(pred.packet_loss_forecast) / max(len(pred.packet_loss_forecast), 1)
            row = [link_id, f"{pred.health_score:.0f}", f"{pred.confidence:.3f}",
                   f"{lat_avg:.1f}", f"{jit_avg:.1f}", f"{pkt_avg:.4f}"]
            for w, val in zip(col_widths, row):
                pdf.cell(w, 6, val, border=1, align="C")
            pdf.ln()

    # Comparison metrics
    pdf.ln(8)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "LSTM Comparison Metrics", ln=True)
    pdf.set_font("Helvetica", "", 9)
    m_on = state.metrics_lstm_on
    m_off = state.metrics_lstm_off
    pdf.cell(0, 6, f"LSTM ON  - Avg Latency: {m_on.avg_latency:.1f}ms, "
                    f"Jitter: {m_on.avg_jitter:.1f}ms, Loss: {m_on.avg_packet_loss:.3f}%, "
                    f"Proactive Steerings: {m_on.proactive_steerings}, "
                    f"Brownouts Avoided: {m_on.brownouts_avoided}", ln=True)
    pdf.cell(0, 6, f"LSTM OFF - Avg Latency: {m_off.avg_latency:.1f}ms, "
                    f"Jitter: {m_off.avg_jitter:.1f}ms, Loss: {m_off.avg_packet_loss:.3f}%, "
                    f"Reactive Steerings: {m_off.reactive_steerings}, "
                    f"Brownouts Hit: {m_off.brownouts_hit}", ln=True)

    return pdf.output()


def generate_steering_events_pdf(limit: int = 100) -> bytes:
    """Generate PDF report of steering events."""
    from fpdf import FPDF

    pdf = FPDF(orientation="L")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "PathWise AI - Steering Events Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(6)

    col_widths = [30, 35, 30, 35, 25, 80, 20]
    headers = ["Time", "Action", "Source", "Target", "Conf", "Reason", "LSTM"]
    pdf.set_font("Helvetica", "B", 8)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 6, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    for evt in list(state.steering_history)[:limit]:
        ts = time.strftime("%H:%M:%S", time.localtime(evt.timestamp))
        reason = evt.reason[:50] + "..." if len(evt.reason) > 50 else evt.reason
        row = [ts, evt.action, evt.source_link, evt.target_link,
               f"{evt.confidence:.2f}", reason, "ON" if evt.lstm_enabled else "OFF"]
        for w, val in zip(col_widths, row):
            pdf.cell(w, 5, val, border=1)
        pdf.ln()

    return pdf.output()


def generate_audit_log_pdf(limit: int = 200) -> bytes:
    """Generate PDF report of audit log."""
    from fpdf import FPDF

    pdf = FPDF(orientation="L")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "PathWise AI - Audit Log Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(6)

    col_widths = [30, 25, 30, 30, 130, 30]
    headers = ["Time", "Type", "Actor", "Link", "Details", "Checksum"]
    pdf.set_font("Helvetica", "B", 8)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 6, h, border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 7)
    entries = audit.get_all_entries_raw()[-limit:]
    for e in entries:
        ts = time.strftime("%H:%M:%S", time.localtime(e.event_time))
        details = (e.details or "")[:80]
        row = [ts, e.event_type, e.actor[:15], e.link_id or "", details, e.checksum[:12] + ".."]
        for w, val in zip(col_widths, row):
            pdf.cell(w, 5, str(val), border=1)
        pdf.ln()

    return pdf.output()
