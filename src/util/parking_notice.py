# -*- coding: utf-8 -*-

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import KeepInFrame, Paragraph, Spacer, Table, TableStyle


pdfmetrics.registerFont(TTFont(
    'ParkingNotice', str(Path(reportlab.__file__).parent / 'fonts' / 'Vera.ttf')))


def generate_notice(business_name, vin, tag, reason, generated_at, events):
    output = BytesIO()
    canvas = Canvas(output, pagesize=(288, 432))
    canvas.setTitle('Parking Violation')
    text_style = ParagraphStyle(
        'notice', fontName='ParkingNotice', fontSize=8, leading=10,
        spaceAfter=4, splitLongWords=True)
    cell_style = ParagraphStyle(
        'event', parent=text_style, fontSize=5.5, leading=7, spaceAfter=0)

    def paragraph(value, style=text_style):
        return Paragraph(escape(str(value or '')).replace('\n', '<br/>'), style)

    content = [
        paragraph('Parking Violation', ParagraphStyle(
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
    frame = KeepInFrame(264, 408, content, mode='shrink', hAlign='LEFT', vAlign='TOP')
    _, height = frame.wrapOn(canvas, 264, 408)
    frame.drawOn(canvas, 12, 420 - height)
    canvas.showPage()
    canvas.save()
    return output.getvalue()
