"""
PDF and CSV report export (Phase 3h).

generate_pdf_report(result_dict)  → bytes  (PDF)
generate_csv_report(result_dict)  → str    (CSV text)

Both accept the dict produced by ValidationResult.to_dict() or a job result.
The PDF is built with reportlab (optional dep); if reportlab is not installed,
generate_pdf_report raises ImportError with a clear install message.
"""

import csv
import io
from datetime import datetime
from typing import Any, Dict, List


# ── CSV export ────────────────────────────────────────────────────────────────

def generate_csv_report(result_dict: Dict[str, Any]) -> str:
    """
    Return a CSV string with one row per validation issue.

    Columns: severity, rule_name, column, row, message
    A summary header block is prepended as comment-style rows.
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')

    # Header block
    summary = result_dict.get('summary', {})
    writer.writerow(['# Medical Data Validation Report'])
    writer.writerow(['# Generated', datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')])
    writer.writerow(['# Status', 'VALID' if result_dict.get('is_valid') else 'INVALID'])
    writer.writerow(['# Total Issues', result_dict.get('total_issues', 0)])
    writer.writerow(['# Errors', result_dict.get('error_count', 0)])
    writer.writerow(['# Warnings', result_dict.get('warning_count', 0)])
    writer.writerow(['# Info', result_dict.get('info_count', 0)])
    writer.writerow(['# Total Rows', summary.get('total_rows', 'N/A')])
    writer.writerow(['# Total Columns', summary.get('total_columns', 'N/A')])
    writer.writerow([])

    # Issue rows
    writer.writerow(['severity', 'rule_name', 'column', 'row', 'message'])
    for issue in result_dict.get('issues', []):
        writer.writerow([
            issue.get('severity', ''),
            issue.get('rule_name', ''),
            issue.get('column', ''),
            issue.get('row', ''),
            issue.get('message', ''),
        ])

    return output.getvalue()


# ── PDF export ────────────────────────────────────────────────────────────────

def generate_pdf_report(result_dict: Dict[str, Any]) -> bytes:
    """
    Return a PDF binary containing the full validation report.

    Requires reportlab.  Install with: pip install reportlab
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
            HRFlowable,
        )
    except ImportError as exc:
        raise ImportError(
            "reportlab is required for PDF export. "
            "Install it with: pip install reportlab"
        ) from exc

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title', parent=styles['Title'], fontSize=18, spaceAfter=12
    )
    heading2 = ParagraphStyle(
        'Heading2', parent=styles['Heading2'], fontSize=13, spaceAfter=6
    )
    normal = styles['Normal']

    # ── severity → colour ────────────────────────────────────────────────────
    sev_colour = {
        'error':   colors.HexColor('#c0392b'),
        'warning': colors.HexColor('#e67e22'),
        'info':    colors.HexColor('#2980b9'),
    }

    is_valid = result_dict.get('is_valid', True)
    summary = result_dict.get('summary', {})
    issues: List[Dict[str, Any]] = result_dict.get('issues', [])
    compliance = summary.get('compliance_report', {})
    timestamp = result_dict.get('timestamp', datetime.utcnow().isoformat())

    story = []

    # Title
    story.append(Paragraph('Medical Data Validation Report', title_style))
    story.append(Paragraph(f'Generated: {timestamp}', normal))
    status_colour = '#27ae60' if is_valid else '#c0392b'
    status_label = 'VALID' if is_valid else 'INVALID'
    story.append(Paragraph(
        f'<font color="{status_colour}"><b>Overall Status: {status_label}</b></font>',
        normal,
    ))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.grey))
    story.append(Spacer(1, 0.3 * cm))

    # Summary table
    story.append(Paragraph('Summary', heading2))
    summary_data = [
        ['Metric', 'Value'],
        ['Total Rows', str(summary.get('total_rows', 'N/A'))],
        ['Total Columns', str(summary.get('total_columns', 'N/A'))],
        ['Total Issues', str(result_dict.get('total_issues', 0))],
        ['Errors', str(result_dict.get('error_count', 0))],
        ['Warnings', str(result_dict.get('warning_count', 0))],
        ['Info', str(result_dict.get('info_count', 0))],
        ['Duplicate Rows', str(summary.get('duplicate_rows', 'N/A'))],
    ]
    t = Table(summary_data, colWidths=[8 * cm, 8 * cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # Compliance summary (if present)
    if compliance and isinstance(compliance, dict):
        story.append(Paragraph('Compliance Summary', heading2))
        comp_rows = [['Standard', 'Score', 'Risk Level', 'Compliant']]
        standards = compliance.get('standards', compliance)
        if isinstance(standards, dict):
            for std_name, std_data in standards.items():
                if std_name in ('all_violations', 'overall_score', 'risk_level',
                                'template_applied'):
                    continue
                if isinstance(std_data, dict) and 'score' in std_data:
                    comp_rows.append([
                        std_name.upper(),
                        f"{std_data.get('score', 0):.1f}",
                        std_data.get('risk_level', 'N/A'),
                        'Yes' if std_data.get('compliant') else 'No',
                    ])
        if len(comp_rows) > 1:
            ct = Table(comp_rows, colWidths=[4 * cm, 3 * cm, 4 * cm, 3 * cm])
            ct.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            story.append(ct)
            story.append(Spacer(1, 0.5 * cm))

    # Issues table
    if issues:
        story.append(Paragraph(f'Validation Issues ({len(issues)} total)', heading2))
        issue_rows = [['Severity', 'Column', 'Row', 'Rule', 'Message']]
        for issue in issues[:200]:
            issue_rows.append([
                issue.get('severity', ''),
                str(issue.get('column', '') or ''),
                str(issue.get('row', '') or ''),
                str(issue.get('rule_name', '') or ''),
                str(issue.get('message', ''))[:80],
            ])
        it = Table(issue_rows, colWidths=[2 * cm, 3 * cm, 1.5 * cm, 3 * cm, 6.5 * cm])
        it.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ecf0f1')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('WORDWRAP', (4, 1), (4, -1), True),
        ]))
        story.append(it)
        if len(issues) > 200:
            story.append(Spacer(1, 0.2 * cm))
            story.append(Paragraph(
                f'(Report shows first 200 of {len(issues)} issues)', normal
            ))
    else:
        story.append(Paragraph('No validation issues found.', normal))

    doc.build(story)
    return buffer.getvalue()


# ── Flask route registration ──────────────────────────────────────────────────

def register_report_routes(app) -> None:
    """Attach /api/report/* routes to a Flask app."""
    from flask import request, jsonify, g, Response

    try:
        from medical_data_validator.auth import login_required
        from medical_data_validator.jobs import get_job
    except ImportError:
        from ..auth import login_required
        from ..jobs import get_job

    def _get_result_dict(run_id: str, tenant: str, role: str):
        """Resolve run_id to a result dict (from job store)."""
        job = get_job(run_id)
        if not job:
            return None, ('Job not found', 404)
        if role != 'admin' and job.get('tenant') != tenant:
            return None, ('Forbidden', 403)
        if job['status'] != 'completed':
            return None, (f"Job is {job['status']}", 409)
        result = job.get('result') or {}
        if not isinstance(result, dict):
            return None, ('Result is not a valid dict', 500)
        return result, None

    @app.route('/api/report/<run_id>/pdf', methods=['GET'])
    @login_required
    def export_pdf(run_id):
        result, err = _get_result_dict(run_id, g.tenant, g.role)
        if err:
            return jsonify({'error': err[0]}), err[1]
        try:
            pdf_bytes = generate_pdf_report(result)
        except ImportError as exc:
            return jsonify({'error': str(exc)}), 500
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="report-{run_id}.pdf"',
                'Content-Length': str(len(pdf_bytes)),
            },
        )

    @app.route('/api/report/<run_id>/csv', methods=['GET'])
    @login_required
    def export_csv(run_id):
        result, err = _get_result_dict(run_id, g.tenant, g.role)
        if err:
            return jsonify({'error': err[0]}), err[1]
        csv_text = generate_csv_report(result)
        return Response(
            csv_text,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="report-{run_id}.csv"',
            },
        )

    @app.route('/api/report/inline/pdf', methods=['POST'])
    @login_required
    def export_inline_pdf():
        """Generate a PDF directly from a posted result_dict (no job needed)."""
        result = request.get_json(silent=True)
        if not result:
            return jsonify({'error': 'No result_dict provided'}), 400
        try:
            pdf_bytes = generate_pdf_report(result)
        except ImportError as exc:
            return jsonify({'error': str(exc)}), 500
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment; filename="report.pdf"'},
        )

    @app.route('/api/report/inline/csv', methods=['POST'])
    @login_required
    def export_inline_csv():
        """Generate a CSV directly from a posted result_dict."""
        result = request.get_json(silent=True)
        if not result:
            return jsonify({'error': 'No result_dict provided'}), 400
        csv_text = generate_csv_report(result)
        return Response(
            csv_text,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename="report.csv"'},
        )
