import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def generate_invoice_pdf(order, customer, payments=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph("INVOICE", ParagraphStyle(name='Title', fontName='Helvetica-Bold', fontSize=18)))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(f"Order # {order.id} &nbsp;&nbsp; Date: {order.created_at.strftime('%Y-%m-%d') if order.created_at else '-'}", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"<b>Customer:</b> {customer.full_name}<br/>Phone: {customer.phone}<br/>Address: {customer.address or '-'}", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(f"<b>Clothing:</b> {order.clothing_type}<br/>Delivery: {order.delivery_date or '-'}", styles['Normal']))
    story.append(Spacer(1, 0.3 * inch))
    total = float(order.total_price or 0)
    advance = float(order.advance_paid or 0)
    balance = total - advance
    data = [
        ['Description', 'Amount'],
        ['Total Order Price', f'{total:.2f}'],
        ['Advance Paid', f'{advance:.2f}'],
        ['Remaining Balance', f'{balance:.2f}'],
    ]
    if payments:
        for p in payments:
            data.insert(-1, [f'Payment ({p.payment_type})', f'{p.amount:.2f}'])
    t = Table(data, colWidths=[3 * inch, 2 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * inch))
    story.append(Paragraph("Thank you for your business.", styles['Normal']))
    doc.build(story)
    buffer.seek(0)
    return buffer
