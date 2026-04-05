"""
PDF invoice — Abjad Super Tailor (product lines, no legacy customer/clothing block).
"""
from __future__ import annotations

import io
import json
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

LINES_PREFIX = 'ABJAD_LINES_JSON:'

# Match invoice_print.html — edit here for PDF branding
BRAND = {
    'name': 'Abjad Super Tailor',
    'address': 'Nairobi - Kenya',
    'phone': '+254 799 824 10',
}


def _stable_invoice_number(order_id: int) -> str:
    x = order_id & 0xFFFFFFFF
    parts = []
    for i in range(12):
        x = ((x * 31) ^ (i * 17) + 0x9E3779B9) & 0xFFFFFFFF
        parts.append(f'{x & 0xFF:02x}')
    return 'INV' + ''.join(parts)[:24]


def _parse_order_lines(fabric_details: str | None):
    if not fabric_details or LINES_PREFIX not in fabric_details:
        return None
    try:
        raw = fabric_details.split(LINES_PREFIX, 1)[1].strip()
        data = json.loads(raw)
        return data.get('lines') or []
    except (json.JSONDecodeError, ValueError, TypeError):
        return None


def generate_invoice_pdf(order, payments=None, seller_email: Optional[str] = None):
    """
    Build a professional A4 PDF matching the Abjad Super Tailor invoice layout.
    Does not print placeholder customer/clothing blocks.
    """
    payments = payments or []
    seller_email = (seller_email or '').strip() or '—'

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.65 * inch,
        leftMargin=0.65 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
    )
    styles = getSampleStyleSheet()

    normal = styles['Normal']
    normal.fontName = 'Helvetica'
    normal.fontSize = 10
    normal.leading = 13

    bold = ParagraphStyle(
        'Bold10',
        parent=normal,
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
    )
    left_header = ParagraphStyle(
        'LeftHeader',
        parent=normal,
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        alignment=0,
    )
    right_meta = ParagraphStyle(
        'RightMeta',
        parent=normal,
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        alignment=2,  # right
    )

    story = []
    usable_w = A4[0] - doc.leftMargin - doc.rightMargin
    col_w = usable_w / 2.0

    date_str = order.created_at.strftime('%m/%d/%Y') if order.created_at else '—'
    inv_no = _stable_invoice_number(order.id)

    # Inline sizes (pt): company name ~12pt semibold; address/phone 10pt; INVOICE ~13pt; meta 10pt
    left_block = (
        f"<b><font size=12>{BRAND['name']}</font></b><br/>"
        f"<font size=10>{BRAND['address']}<br/>{BRAND['phone']}</font>"
    )
    right_block = (
        f"<b><font size=13>INVOICE</font></b><br/>"
        f"<font size=10>Date: {date_str}<br/>"
        f"Invoice #:<br/>{inv_no}</font>"
    )

    header_tbl = Table(
        [
            [
                Paragraph(left_block, left_header),
                Paragraph(right_block, right_meta),
            ]
        ],
        colWidths=[col_w, col_w],
    )
    header_tbl.setStyle(
        TableStyle(
            [
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(header_tbl)
    story.append(Spacer(1, 0.18 * inch))

    seller_html = f"<b>Seller:</b><br/>{BRAND['name']}<br/>{seller_email}"
    story.append(Paragraph(seller_html, normal))
    story.append(Spacer(1, 0.14 * inch))

    # Full-width horizontal rule
    rule = Table([['']], colWidths=[usable_w], rowHeights=[1])
    rule.setStyle(
        TableStyle(
            [
                ('LINEABOVE', (0, 0), (-1, -1), 0.75, colors.black),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(rule)
    story.append(Spacer(1, 0.16 * inch))

    lines = _parse_order_lines(order.fabric_details)
    rows_data = [['DESCRIPTION', 'QTY', 'PRICE', 'TOTAL']]
    grey_header = colors.Color(0.925, 0.933, 0.945)

    if lines:
        for L in lines:
            qty = float(L.get('qty') or 0)
            price = float(L.get('price') or 0)
            line_total = qty * price
            desc = (L.get('product') or '—').strip() or '—'
            rows_data.append(
                [
                    desc,
                    f'{qty:g}' if qty == int(qty) else f'{qty:.2f}',
                    f'{price:,.2f}',
                    f'{line_total:,.2f}',
                ]
            )
    else:
        desc = (order.clothing_type or 'Item').strip() or 'Item'
        total = float(order.total_price or 0)
        rows_data.append([desc, '1', f'{total:,.2f}', f'{total:,.2f}'])

    # Column widths: description flexible
    cw = usable_w
    t_cols = [cw * 0.46, cw * 0.12, cw * 0.21, cw * 0.21]

    items_tbl = Table(rows_data, colWidths=t_cols, repeatRows=1)
    items_tbl.setStyle(
        TableStyle(
            [
                ('BACKGROUND', (0, 0), (-1, 0), grey_header),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('TOPPADDING', (0, 0), (-1, 0), 10),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.Color(0.78, 0.82, 0.86)),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 9),
            ]
        )
    )
    story.append(items_tbl)
    story.append(Spacer(1, 0.22 * inch))

    grand = float(order.total_price or 0)
    total_para = Paragraph(f"<b>Total:</b> &nbsp; <b>{grand:,.2f}</b>", bold)
    total_tbl = Table([[Paragraph('', normal), total_para]], colWidths=[cw * 0.55, cw * 0.45])
    total_tbl.setStyle(
        TableStyle(
            [
                ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(total_tbl)

    doc.build(story)
    buffer.seek(0)
    return buffer
