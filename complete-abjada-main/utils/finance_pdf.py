"""
Professional PDF documents for finance: receipts, invoices, and section reports.
Uses ReportLab; branding aligned with utils.invoice.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Callable, List, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from utils.invoice import BRAND

ACCENT = colors.HexColor('#059669')
SLATE = colors.HexColor('#0f172a')
GREY_HEADER = colors.Color(0.925, 0.933, 0.945)
GRID = colors.Color(0.78, 0.82, 0.86)


def _fmt_money(n: Any, currency: str = 'KES') -> str:
    try:
        v = float(n or 0)
    except (TypeError, ValueError):
        v = 0.0
    return f'{v:,.2f} {currency}'


def _method_label(m: Any) -> str:
    x = str(m or 'cash').lower().replace(' ', '_').replace('-', '')
    if x in ('mpesa', 'mobile_money', 'digital', 'bank'):
        return 'M-Pesa'
    return 'Cash'


def _dt_str(iso: Any) -> str:
    if not iso:
        return '—'
    s = str(iso).replace('T', ' ')[:19]
    return s


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.HexColor('#64748b'))
    canvas.setFont('Helvetica', 8)
    text = f'{BRAND["name"]} · Generated {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")} · Page {doc.page}'
    canvas.drawString(doc.leftMargin, 0.42 * inch, text)
    canvas.restoreState()


def _header_band(story, styles, title: str, subtitle: str):
    """Top title strip with brand accent."""
    normal = styles['Normal']
    title_style = ParagraphStyle(
        'FinTitle',
        parent=normal,
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=SLATE,
    )
    sub_style = ParagraphStyle(
        'FinSub',
        parent=normal,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#64748b'),
    )
    brand_line = ParagraphStyle(
        'BrandLine',
        parent=normal,
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=ACCENT,
    )
    story.append(Paragraph(BRAND['name'], brand_line))
    story.append(Paragraph(f'{BRAND["address"]} · {BRAND["phone"]}', sub_style))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph(title, title_style))
    if subtitle:
        story.append(Paragraph(subtitle, sub_style))
    story.append(Spacer(1, 0.2 * inch))


def _data_table(story, col_widths: Sequence[float], headers: List[str], rows: List[List[str]]):
    data = [headers] + rows
    t = Table(data, colWidths=list(col_widths), repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), SLATE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.45, GRID),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 7),
                ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                ('TOPPADDING', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 7),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.98, 0.99, 0.99)]),
            ]
        )
    )
    story.append(t)


def _build_pdf(story_fn: Callable[[Any, Any], None]) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
    )
    styles = getSampleStyleSheet()
    story = []
    story_fn(doc, styles, story)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer


# --- Single transaction documents ---


def pdf_transaction_receipt(t: dict) -> io.BytesIO:
    """Payment receipt for money received (Account received)."""

    def body(doc, styles, story):
        amt = _fmt_money(t.get('amount'), t.get('currency') or 'KES')
        sub = f'Reference: TX-{t.get("id", "—")} · {_dt_str(t.get("transaction_date") or t.get("created_at"))}'
        _header_band(story, styles, 'PAYMENT RECEIPT', sub)
        cp = (t.get('counterparty') or '—').strip() or '—'
        det = (t.get('details') or '—').strip() or '—'
        rows = [
            ['Received from', cp],
            ['Amount', amt],
            ['Payment method', _method_label(t.get('method'))],
            ['Category', (t.get('category') or '—').strip() or '—'],
            ['Note / details', det[:500]],
        ]
        w = (A4[0] - doc.leftMargin - doc.rightMargin) / 2.0
        tb = Table([[Paragraph(f'<b>{a}</b>', styles['Normal']), Paragraph(str(b), styles['Normal'])] for a, b in rows], colWidths=[w * 0.38, w * 0.62])
        tb.setStyle(
            TableStyle(
                [
                    ('GRID', (0, 0), (-1, -1), 0.4, GRID),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (0, 0), (0, -1), colors.Color(0.96, 0.98, 0.97)),
                ]
            )
        )
        story.append(tb)
        story.append(Spacer(1, 0.25 * inch))
        story.append(
            Paragraph(
                '<i>This receipt confirms payment recorded in Abjad Super Tailor financial accounts.</i>',
                ParagraphStyle('Foot', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#64748b')),
            )
        )

    return _build_pdf(body)


def pdf_transaction_invoice(t: dict) -> io.BytesIO:
    """Invoice / statement for accounts receivable."""

    def body(doc, styles, story):
        amt = float(t.get('amount') or 0)
        pa = t.get('paid_amount')
        try:
            pa_f = float(pa) if pa is not None else 0.0
        except (TypeError, ValueError):
            pa_f = 0.0
        due = max(0.0, amt - pa_f)
        cur = t.get('currency') or 'KES'
        sub = f'Document: TX-{t.get("id", "—")} · Date: {_dt_str(t.get("transaction_date") or t.get("created_at"))}'
        _header_band(story, styles, 'INVOICE — ACCOUNTS RECEIVABLE', sub)
        cust = (t.get('counterparty') or '—').strip() or '—'
        ps = (t.get('payment_status') or 'unpaid').strip().lower()
        rows = [
            ['Bill to', cust],
            ['Total amount', _fmt_money(amt, cur)],
            ['Amount collected', _fmt_money(pa_f, cur) if pa is not None else '—'],
            ['Balance due', _fmt_money(due, cur)],
            ['Status', ps.title()],
            ['Payment method (when paid)', _method_label(t.get('method'))],
            ['Details', ((t.get('details') or '—').strip() or '—')[:480]],
        ]
        w = A4[0] - doc.leftMargin - doc.rightMargin
        cw = w / 2.0
        tb = Table(
            [[Paragraph(f'<b>{a}</b>', styles['Normal']), Paragraph(str(b), styles['Normal'])] for a, b in rows],
            colWidths=[cw * 0.36, cw * 0.64],
        )
        tb.setStyle(
            TableStyle(
                [
                    ('GRID', (0, 0), (-1, -1), 0.4, GRID),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (0, 0), (0, -1), colors.Color(0.96, 0.97, 1.0)),
                ]
            )
        )
        story.append(tb)
        story.append(Spacer(1, 0.2 * inch))
        story.append(
            Paragraph(
                '<i>Please remit the balance due according to agreed terms. Thank you for your business.</i>',
                ParagraphStyle('Foot', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor('#64748b')),
            )
        )

    return _build_pdf(body)


def pdf_transaction_liability(t: dict) -> io.BytesIO:
    """Creditor / liability record."""

    def body(doc, styles, story):
        sub = f'Reference: TX-{t.get("id", "—")} · {_dt_str(t.get("transaction_date") or t.get("created_at"))}'
        _header_band(story, styles, 'LIABILITY RECORD', sub)
        cred = (t.get('counterparty') or '—').strip() or '—'
        rows = [
            ['Creditor / supplier', cred],
            ['Amount recorded', _fmt_money(t.get('amount'), t.get('currency') or 'KES')],
            ['Status', (t.get('payment_status') or '—').strip() or '—'],
            ['Details', ((t.get('details') or '—').strip() or '—')[:500]],
        ]
        w = A4[0] - doc.leftMargin - doc.rightMargin
        tb = Table(
            [[Paragraph(f'<b>{a}</b>', styles['Normal']), Paragraph(str(b), styles['Normal'])] for a, b in rows],
            colWidths=[w * 0.35, w * 0.65],
        )
        tb.setStyle(
            TableStyle(
                [
                    ('GRID', (0, 0), (-1, -1), 0.4, GRID),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('BACKGROUND', (0, 0), (0, -1), colors.Color(1.0, 0.97, 0.95)),
                ]
            )
        )
        story.append(tb)

    return _build_pdf(body)


# --- List reports ---


def _report_intro(story, styles, report_name: str, period: str):
    _header_band(story, styles, report_name, period)


def pdf_received_report(rows: List[dict], date_from: Optional[str], date_to: Optional[str]) -> io.BytesIO:
    def body(doc, styles, story):
        period = 'All dates'
        if date_from or date_to:
            period = f'Period: {date_from or "…"} to {date_to or "…"}'
        _report_intro(story, styles, 'RECEIVED PAYMENTS REPORT', period)
        total = 0.0
        table_rows = []
        for r in rows:
            try:
                a = float(r.get('amount') or 0)
            except (TypeError, ValueError):
                a = 0.0
            total += a
            table_rows.append(
                [
                    _fmt_money(a, r.get('currency') or 'KES'),
                    _method_label(r.get('method')),
                    str(r.get('counterparty') or '—')[:42],
                    _dt_str(r.get('transaction_date') or r.get('created_at')),
                    str(r.get('details') or '—')[:56],
                ]
            )
        uw = A4[0] - doc.leftMargin - doc.rightMargin
        _data_table(
            story,
            [uw * 0.16, uw * 0.14, uw * 0.22, uw * 0.18, uw * 0.30],
            ['Amount', 'Method', 'Customer', 'Date', 'Details'],
            table_rows,
        )
        story.append(Spacer(1, 0.15 * inch))
        story.append(
            Paragraph(f'<b>Total received:</b> {_fmt_money(total, "KES")}', ParagraphStyle('Tot', parent=styles['Normal'], fontSize=11, textColor=SLATE))
        )

    return _build_pdf(body)


def pdf_receivable_report(rows: List[dict]) -> io.BytesIO:
    def body(doc, styles, story):
        _report_intro(story, styles, 'ACCOUNTS RECEIVABLE REPORT', 'Outstanding customer balances')
        total_amt = 0.0
        total_due = 0.0
        table_rows = []
        for r in rows:
            amt = float(r.get('amount') or 0)
            pa = r.get('paid_amount')
            pa_f = float(pa) if pa is not None else 0.0
            due = float(r.get('balance_due') if r.get('balance_due') is not None else max(0, amt - pa_f))
            total_amt += amt
            total_due += due
            table_rows.append(
                [
                    _fmt_money(amt, 'KES'),
                    _fmt_money(pa_f, 'KES') if pa is not None else '—',
                    _fmt_money(due, 'KES'),
                    _method_label(r.get('method')),
                    str(r.get('customer_name') or '—')[:36],
                    _dt_str(r.get('transaction_date')),
                    str(r.get('payment_status') or '—'),
                ]
            )
        uw = A4[0] - doc.leftMargin - doc.rightMargin
        _data_table(
            story,
            [uw * 0.12, uw * 0.12, uw * 0.12, uw * 0.11, uw * 0.18, uw * 0.13, uw * 0.12],
            ['Amount', 'Paid', 'Due', 'Method', 'Customer', 'Date', 'Status'],
            table_rows,
        )
        story.append(Spacer(1, 0.12 * inch))
        story.append(
            Paragraph(
                f'<b>Total invoiced:</b> {_fmt_money(total_amt, "KES")} &nbsp;·&nbsp; <b>Total balance due:</b> {_fmt_money(total_due, "KES")}',
                ParagraphStyle('Tot', parent=styles['Normal'], fontSize=10, textColor=SLATE),
            )
        )

    return _build_pdf(body)


def pdf_liabilities_report(rows: List[dict]) -> io.BytesIO:
    def body(doc, styles, story):
        _report_intro(story, styles, 'LIABILITIES REPORT', 'Amounts owed to creditors / suppliers')
        total = 0.0
        table_rows = []
        for r in rows:
            a = float(r.get('amount') or 0)
            total += a
            table_rows.append(
                [
                    _fmt_money(a, 'KES'),
                    str(r.get('creditor_name') or '—')[:44],
                    _dt_str(r.get('transaction_date')),
                    str(r.get('status') or '—'),
                    str(r.get('details') or '—')[:40],
                ]
            )
        uw = A4[0] - doc.leftMargin - doc.rightMargin
        _data_table(
            story,
            [uw * 0.16, uw * 0.26, uw * 0.18, uw * 0.12, uw * 0.28],
            ['Amount', 'Creditor', 'Date', 'Status', 'Details'],
            table_rows,
        )
        story.append(Spacer(1, 0.12 * inch))
        story.append(Paragraph(f'<b>Total liabilities:</b> {_fmt_money(total, "KES")}', ParagraphStyle('Tot', parent=styles['Normal'], fontSize=11, textColor=SLATE)))

    return _build_pdf(body)


def pdf_expenses_report(rows: List[dict], date_from: Optional[str], date_to: Optional[str]) -> io.BytesIO:
    def body(doc, styles, story):
        period = 'All dates'
        if date_from or date_to:
            period = f'Period: {date_from or "…"} to {date_to or "…"}'
        _report_intro(story, styles, 'EXPENSES REPORT', period)
        total = 0.0
        table_rows = []
        for r in rows:
            a = float(r.get('amount') or 0)
            total += a
            table_rows.append(
                [
                    str(r.get('category') or '—')[:28],
                    _fmt_money(a, 'KES'),
                    str(r.get('expense_date') or '—')[:12],
                    str(r.get('description') or '—')[:52],
                ]
            )
        uw = A4[0] - doc.leftMargin - doc.rightMargin
        _data_table(story, [uw * 0.22, uw * 0.16, uw * 0.14, uw * 0.48], ['Category', 'Amount', 'Date', 'Description'], table_rows)
        story.append(Spacer(1, 0.12 * inch))
        story.append(Paragraph(f'<b>Total expenses:</b> {_fmt_money(total, "KES")}', ParagraphStyle('Tot', parent=styles['Normal'], fontSize=11, textColor=SLATE)))

    return _build_pdf(body)
