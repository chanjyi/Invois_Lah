"""Actual downloadable local invoice PDF. Intentionally no official LHDN QR."""
from __future__ import annotations
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from invoice_logic import fmt, totals

DARK = colors.HexColor('#173728')
SAGE = colors.HexColor('#ADD47E')

def invoice_pdf(invoice: dict, items: list[dict], supplier: dict, logo_bytes: bytes | None = None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=17*mm, leftMargin=17*mm,
                            topMargin=17*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BrandBig', fontName='Helvetica-Bold', fontSize=22, textColor=DARK, spaceAfter=8))
    styles.add(ParagraphStyle(name='MetaSmall2', fontName='Helvetica', fontSize=9, leading=14, textColor=colors.HexColor('#56665d')))
    styles.add(ParagraphStyle(name='TableText2', fontName='Helvetica', fontSize=9, leading=12))
    styles.add(ParagraphStyle(name='RightValue2', fontName='Helvetica-Bold', fontSize=10, alignment=TA_RIGHT))
    P = lambda value, style='MetaSmall2': Paragraph(escape(str(value or '')).replace('\n', '<br/>'), styles[style])
    content = [P('INVOICE', 'BrandBig'), P('Local invoice copy — NOT a validated LHDN e-Invoice'), Spacer(1, 7*mm)]
    if logo_bytes:
        try:
            logo = RLImage(BytesIO(logo_bytes), width=28*mm, height=28*mm, kind='proportional')
            logo.hAlign = 'LEFT'
            content.extend([logo, Spacer(1, 4*mm)])
        except Exception:
            pass  # Optional branding must not block PDF export.
    seller_address = ', '.join(str(supplier.get(k) or '') for k in ['address', 'city', 'postcode', 'state_code', 'country_code'])
    buyer_address = ', '.join(str(invoice.get(k) or '') for k in ['client_address','client_city','client_postcode','client_state_code','client_country_code'])
    header = Table([
        [P('FROM', 'TableText2'), P('BILL TO', 'TableText2')],
        [P(supplier.get('name')), P(invoice.get('client_name'))],
        [P(seller_address), P(buyer_address)],
        [P(f"TIN: {supplier.get('tin','—')}"), P(f"TIN: {invoice.get('client_tin','—')}")],
        [P(f"{supplier.get('id_type','ID')}: {supplier.get('id_number','—')}"),
         P(f"{invoice.get('client_id_type','ID')}: {invoice.get('client_id_number','—')}")],
        [P(f"MSIC: {supplier.get('msic','—')}"), P(f"Phone: {invoice.get('client_phone','—')}")],
        [P(f"Phone: {supplier.get('phone','—')}"), P(invoice.get('client_email',''))],
    ], colWidths=[88*mm, 88*mm], hAlign='LEFT')
    header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'), ('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    content += [header, Spacer(1,4*mm),
                P(f"Invoice #: {invoice['invoice_number']}"),
                P(f"Issued: {invoice['issue_date']}    Due: {invoice['due_date']}    Currency: {invoice['currency']}"),
                Spacer(1,7*mm)]
    tdata = [[P('Description','TableText2'), P('Qty','TableText2'), P('Unit price','TableText2'),
              P('Tax','TableText2'), P('Amount','TableText2')]]
    for item in items:
        desc = str(item['description']) + f"  (Class: {item.get('classification_code','—')})"
        tdata.append([P(desc,'TableText2'), P(item['quantity']),
                      P(fmt(item['unit_price'], invoice['currency'])),
                      P(f"{item.get('tax_type','06')} / {item.get('tax_rate','0')}%"),
                      P(fmt(item['amount'], invoice['currency']))])
    table = Table(tdata, colWidths=[73*mm,16*mm,32*mm,22*mm,33*mm], repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),SAGE), ('TEXTCOLOR',(0,0),(-1,0),DARK),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white, colors.HexColor('#f4f9f0')]),
        ('VALIGN',(0,0),(-1,-1),'TOP'), ('TOPPADDING',(0,0),(-1,-1),9),
        ('BOTTOMPADDING',(0,0),(-1,-1),9), ('LINEBELOW',(0,-1),(-1,-1),0.5,colors.HexColor('#dce5d6')),
    ]))
    content += [table, Spacer(1,8*mm)]
    calc = totals(items, invoice.get('discount_percent') or 0, invoice.get('shipping_fee') or 0)
    trows = [('Subtotal', calc['subtotal']), ('Discount', -calc['discount']),
             ('Additional fees',calc['shipping']), ('Line item tax',calc['tax']), ('TOTAL',calc['total'])]
    tt = Table([[P(k, 'TableText2'), P(fmt(v, invoice['currency']), 'RightValue2')] for k,v in trows], colWidths=[125*mm, 51*mm])
    tt.setStyle(TableStyle([('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#ebf5df')),
                            ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
    content.append(tt)
    if invoice.get('notes'):
        content.extend([Spacer(1,5*mm), P('Notes: '+invoice['notes'])])
    content.extend([Spacer(1,8*mm), P('Payment status: '+invoice.get('payment_status','').upper()),
                    P('LHDN status: NOT SUBMITTED. This PDF is not proof of MyInvois validation.')])
    doc.build(content)
    return buf.getvalue()
