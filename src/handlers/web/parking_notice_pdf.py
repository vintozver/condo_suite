# -*- coding: utf-8 -*-

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import KeepInFrame, Paragraph, Spacer, Table, TableStyle


pdfmetrics.registerFont(TTFont(
    'ParkingNotice', str(Path(reportlab.__file__).parent / 'fonts' / 'Vera.ttf')))


def generate_notice(business_name, vin, tag, reason, generated_at, events):
    page_width, page_height = 4 * inch, 6 * inch
    margin = inch / 6
    content_width = page_width - 2 * margin
    content_height = page_height - 2 * margin
    output = BytesIO()
    canvas = Canvas(output, pagesize=(page_width, page_height))
    canvas.setTitle('Parking Notice')
    # Font sizes, column widths, spacing, and padding are in PDF points (72 per inch).
    text_style = ParagraphStyle(
        'notice', fontName='ParkingNotice', fontSize=8, leading=10,
        spaceAfter=4, splitLongWords=True)
    cell_style = ParagraphStyle(
        'event', parent=text_style, fontSize=5.5, leading=7, spaceAfter=0)

    def paragraph(value, style=text_style):
        return Paragraph(escape(str(value or '')).replace('\n', '<br/>'), style)

    content = [
        paragraph('Parking Notice', ParagraphStyle(
            'title', parent=text_style, fontSize=16, leading=19)),
        paragraph(business_name, ParagraphStyle(
            'business', parent=text_style, fontSize=10, leading=12)),
        Spacer(1, 4),
        paragraph('VIN: %s' % vin),
        paragraph('Tag: %s' % tag),
        paragraph('Reason: %s' % reason),
        paragraph('Generated: %s' % generated_at.strftime('%Y-%m-%d %H:%M:%S %Z %z')),
        Spacer(1, 4),
        paragraph('Last 20 parking events'),
    ]
    rows = [[paragraph(label, cell_style) for label in ('DT', 'Tag', 'Reason', 'Remarks')]]
    for event in events[:20]:
        rows.append([
            paragraph(event['dt'].strftime('%Y-%m-%d\n%H:%M %Z'), cell_style),
            paragraph(event['tag'], cell_style),
            paragraph(event['reason'], cell_style),
            paragraph(event['remarks'], cell_style),
        ])
    table = Table(rows, colWidths=(63, 39, 65, 97), hAlign='LEFT')
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    content.append(table)
    if not events:
        content.append(paragraph('No parking events.'))

    # Fit variable-length fields and all 20 rows onto a single 4x6-inch page.
    frame = KeepInFrame(content_width, content_height, content,
                        mode='shrink', hAlign='LEFT', vAlign='TOP')
    _, height = frame.wrapOn(canvas, content_width, content_height)
    frame.drawOn(canvas, margin, page_height - margin - height)
    canvas.showPage()
    canvas.save()
    return output.getvalue()
