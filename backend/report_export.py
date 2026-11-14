"""PDF export of the same Markdown used by the FIELDWISE browser report.

The renderer does not execute Markdown/HTML, does not change engine outputs and does
not write report files on the server. SVG-equivalent comparison and historical
figures are drawn as selectable-resolution PDF vectors from saved report values.
"""
from __future__ import annotations

from io import BytesIO
from html import escape
from pathlib import Path
import math
import re
import sys
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

INK = colors.HexColor('#1f3d2c')
GREEN = colors.HexColor('#27754d')
MUTED = colors.HexColor('#577465')
PALE = colors.HexColor('#e9f3e7')
RULE = colors.HexColor('#dae7d9')


def _fonts() -> tuple[str, str]:
    """Use a Unicode font when available; PDF output never depends on the host."""
    candidates = [
        (Path('C:/Windows/Fonts/arial.ttf'), Path('C:/Windows/Fonts/arialbd.ttf')),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')),
        (Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf'), Path('/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf')),
    ]
    for regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            try:
                pdfmetrics.registerFont(TTFont('FW-Regular', str(regular)))
                pdfmetrics.registerFont(TTFont('FW-Bold', str(bold)))
                pdfmetrics.registerFontFamily('FW-Regular', normal='FW-Regular', bold='FW-Bold')
                return 'FW-Regular', 'FW-Bold'
            except Exception:
                continue
    return 'Helvetica', 'Helvetica-Bold'


def _numeric(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _clean(text: object) -> str:
    """Make reserved markup safe, preserving Unicode when possible."""
    return xml_escape(str(text if text is not None else ''))


def _inline(text: str) -> str:
    # All raw HTML is escaped. Only minimal Markdown emphasis is recognized.
    safe = _clean(text)
    safe = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', safe)
    safe = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', safe)
    return safe


class BarFigure(Flowable):
    def __init__(self, label: str, metric: dict, entries: list[dict], width: float, bold: str, regular: str):
        super().__init__()
        self.label, self.metric, self.entries = label, metric, entries
        self.width, self.height = width, 108
        self.bold, self.regular = bold, regular

    def draw(self):
        c = self.canv
        c.setFillColor(INK); c.setFont(self.bold, 8.8)
        c.drawString(0, 94, self.label[:85])
        values = [_numeric(r.get('metrics', {}).get(self.metric['key'])) for r in self.entries]
        valid = [v for v in values if v is not None]
        if not valid:
            c.setFont(self.regular, 8); c.drawString(0, 60, 'Indicator unavailable in this report.')
            return
        lo, hi = min(0, *valid), max(0, *valid)
        span = max(hi-lo, 1e-9)
        start_x, plot_w = 104, self.width-210
        zero_x = start_x + plot_w*(0-lo)/span
        c.setStrokeColor(RULE); c.line(zero_x, 22, zero_x, 82)
        for i, (item, value) in enumerate(zip(self.entries[:3], values[:3])):
            y = 73-23*i
            c.setFont(self.regular, 8); c.setFillColor(MUTED)
            c.drawString(0, y, ['Current','Alternative 1','Alternative 2'][i])
            if value is None:
                c.drawRightString(self.width, y, 'N/A'); continue
            x = start_x + plot_w*(value-lo)/span
            c.setFillColor(colors.HexColor('#9ebba5') if i == 0 else GREEN)
            c.roundRect(min(x, zero_x), y-2, max(1, abs(x-zero_x)), 11, 2.5, fill=1, stroke=0)
            suffix = self.metric.get('unit', '')
            display = f'{value*100:.1f}%' if self.metric.get('isPercent') else f'{value:,.2f} {suffix}'.strip()
            c.setFillColor(INK); c.setFont(self.bold, 8)
            c.drawRightString(self.width, y, display)
        c.setStrokeColor(RULE); c.line(0, 6, self.width, 6)


class HistoricalFigure(Flowable):
    def __init__(self, label: str, metric: dict, lines: list[dict], width: float, bold: str, regular: str):
        super().__init__()
        self.label, self.metric, self.lines = label, metric, lines
        self.width, self.height = width, 191
        self.bold, self.regular = bold, regular

    def draw(self):
        c=self.canv
        c.setFillColor(INK); c.setFont(self.bold, 9)
        c.drawString(0, 174, self.label[:105])
        points=[]
        for series in self.lines:
            for p in series.get('points', []):
                year=_numeric(p.get('startYear'))
                value=_numeric(p.get(self.metric['key']))
                if year is not None and value is not None:
                    points.append((year,value*self.metric['factor']))
        if len(set(x for x,_ in points)) < 2:
            c.setFont(self.regular,8);c.drawString(0,90,'Historical series not available.'); return
        min_year,max_year=min(x for x,_ in points),max(x for x,_ in points)
        min_val,max_val=min(y for _,y in points),max(y for _,y in points)
        pad=max((max_val-min_val)*.12,.001)
        min_val-=pad;max_val+=pad
        left,right,bottom,top=72,self.width-15,35,155
        xfunc=lambda year:left+(year-min_year)/(max_year-min_year)*(right-left)
        yfunc=lambda value:bottom+(value-min_val)/(max_val-min_val)*(top-bottom)
        c.setFont(self.regular,7)
        for k in range(4):
            val=min_val+(max_val-min_val)*k/3
            y=yfunc(val)
            c.setStrokeColor(RULE); c.line(left,y,right,y)
            c.setFillColor(MUTED);c.drawRightString(left-7,y-2,f'{val:,.1f}')
        cols=['#8d9d93','#247a4b','#bc843e']
        for i,series in enumerate(self.lines[:3]):
            data=[]
            for p in series.get('points',[]):
                x=_numeric(p.get('startYear'))
                y=_numeric(p.get(self.metric['key']))
                if x is not None and y is not None: data.append((x,y*self.metric['factor']))
            if len(data)<2:continue
            c.setStrokeColor(colors.HexColor(cols[i])); c.setLineWidth(1.8)
            data.sort()
            path=c.beginPath();path.moveTo(xfunc(data[0][0]),yfunc(data[0][1]))
            for x,y in data[1:]:path.lineTo(xfunc(x),yfunc(y))
            c.drawPath(path)
        c.setFillColor(MUTED);c.setFont(self.regular,7)
        c.drawString(left,23,str(int(min_year)));c.drawRightString(right,23,str(int(max_year)))
        c.drawString(0,6,'Current   /   Alternative 1   /   Alternative 2   |   '+self.metric['unit'][:42])


def _chart_figures(report: dict, styles:dict, available_width: float, bold: str, regular: str):
    results=report.get('results') or {}
    entries=[results.get('current') or {}, *(results.get('alternatives') or [])[:2]]
    enabled=(report.get('inputs') or {}).get('advancedEconomics') is not False
    metrics=[
        {'key':'relativeYieldMedian','label':'Median relative yield','unit':'%','isPercent':True},
        {'key':'relativeYieldWorst','label':'Worst-year relative yield','unit':'%','isPercent':True},
        {'key':'relativeYieldP10','label':'10th-percentile relative yield','unit':'%','isPercent':True},
        {'key':'irrigationMm','label':'Irrigation demand','unit':'mm'},
        {'key':'fertilizerKgN','label':'Nitrogen fertilizer','unit':'kg N/ha'},
        {'key':'nitrogenLeachingKgN','label':'Nitrogen leaching','unit':'kg N/ha'},
        {'key':'humusChangeTonsHa','label':'Annual humus change','unit':'t/ha/year'},
    ]
    if enabled:metrics.append({'key':'grossMarginEurHa','label':'Partial gross margin','unit':'EUR/ha/year'})
    out=[]
    for m in metrics:
        out.append(KeepTogether([BarFigure(m['label'],m,entries,available_width,bold,regular),Spacer(1,7)]))
    return out


def _historical_figures(report:dict,width:float,bold:str,regular:str):
    results=report.get('results') or {}
    series=(results.get('historicalWindows') or {}).get('series') or []
    if not series:return []
    enabled=(report.get('inputs') or {}).get('advancedEconomics') is not False
    metrics=[
      {'key':'relativeYield','label':'Relative yield by historical rotation window','factor':100,'unit':'%'},
      {'key':'irrigationMm','label':'Irrigation demand by historical rotation window','factor':1,'unit':'mm/year'},
      {'key':'humusChangeTonsHa','label':'Annual humus change by historical rotation window','factor':1,'unit':'t/ha/year'},
    ]
    if enabled: metrics.append({'key':'grossMarginEurHa','label':'Partial margin by historical rotation window','factor':1,'unit':'EUR/ha/year'})
    return [KeepTogether([HistoricalFigure(m['label'],m,series,width,bold,regular),Spacer(1,10)]) for m in metrics]


def render_pdf(markdown: str, report:dict, demo:bool=False) -> bytes:
    """Transform supported Markdown + report chart values into a direct A4 PDF."""
    if len(markdown)>1_000_000:raise ValueError('Markdown is too large for PDF export.')
    regular,bold=_fonts()
    styles={
        'normal':ParagraphStyle('FWNormal',fontName=regular,fontSize=9.2,leading=14,textColor=INK,spaceAfter=10,splitLongWords=1),
        'h1':ParagraphStyle('FWH1',fontName=bold,fontSize=20.2,leading=25,textColor=INK,spaceBefore=3,spaceAfter=14,keepWithNext=True),
        'h2':ParagraphStyle('FWH2',fontName=bold,fontSize=13.2,leading=17,textColor=GREEN,spaceBefore=19,spaceAfter=8,keepWithNext=True),
        'h3':ParagraphStyle('FWH3',fontName=bold,fontSize=10.8,leading=15,textColor=GREEN,spaceBefore=12,spaceAfter=6,keepWithNext=True),
        'h4':ParagraphStyle('FWH4',fontName=bold,fontSize=9.8,leading=13,textColor=GREEN,spaceBefore=9,spaceAfter=5,keepWithNext=True),
        'cell':ParagraphStyle('FWCell',fontName=regular,fontSize=7,leading=10.4,textColor=INK,splitLongWords=1),
        'tablehead':ParagraphStyle('FWTableHead',fontName=bold,fontSize=7.3,leading=10.6,textColor=INK,splitLongWords=1),
        'bullet':ParagraphStyle('FWBullet',fontName=regular,fontSize=9,leading=13.5,leftIndent=13,firstLineIndent=-9,spaceAfter=5,textColor=INK),
    }
    buffer=BytesIO()
    doc=SimpleDocTemplate(buffer,pagesize=A4,leftMargin=47,rightMargin=47,topMargin=59,bottomMargin=54,
         title='FIELDWISE | Field Analysis Report',author='FIELDWISE',pageCompression=1)
    width=doc.width
    story=[];lines=markdown.splitlines(); paragraph=[]
    def flush():
        if paragraph:
            story.append(Paragraph(_inline(' '.join(paragraph)),styles['normal']))
            paragraph.clear()
    i=0
    while i<len(lines):
        raw=lines[i];line=raw.strip()
        if not line:
            flush();i+=1;continue
        if line=='<!-- FIELDWISE_CHARTS -->':
            flush();story.extend(_chart_figures(report,styles,width,bold,regular));i+=1;continue
        if line=='<!-- FIELDWISE_HISTORICAL_CHARTS -->':
            flush();story.extend(_historical_figures(report,width,bold,regular));i+=1;continue
        match=re.match(r'^(#{1,4})\s+(.+)',line)
        if match:
            flush();story.append(Paragraph(_inline(match.group(2)),styles['h'+str(len(match.group(1)))]));i+=1;continue
        if line.startswith('|') and line.endswith('|'):
            flush();rows=[]
            while i<len(lines):
                cur=lines[i].strip()
                if not (cur.startswith('|') and cur.endswith('|')):break
                if not re.fullmatch(r'\|[\s|:\-]+\|',cur):
                    cells=[cell.replace('\\|','|').strip() for cell in re.split(r'(?<!\\)\|',cur[1:-1])]
                    rows.append(cells)
                i+=1
            if rows:
                count=max(len(row) for row in rows)
                widths=([width*.32]+[width*.68/(count-1)]*(count-1)) if count>1 else [width]
                # Narrow numeric comparison: prioritize indicator name while preserving wide text cells.
                if count>=5:widths=[width*.27]+[width*.73/(count-1)]*(count-1)
                data=[]
                for ri,row in enumerate(rows):
                    data.append([Paragraph(_inline(row[ci] if ci<len(row) else ''),styles['tablehead' if ri==0 else 'cell']) for ci in range(count)])
                table=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT',splitByRow=1)
                table.setStyle(TableStyle([
                    ('VALIGN',(0,0),(-1,-1),'TOP'),
                    ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
                    ('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),
                    ('BACKGROUND',(0,0),(-1,0),PALE),
                    ('LINEBELOW',(0,0),(-1,0),.6,GREEN),
                    ('LINEBELOW',(0,1),(-1,-2),.25,RULE),
                ]))
                story.append(table);story.append(Spacer(1,12))
            continue
        if line.startswith('- '):
            flush();story.append(Paragraph('&#8226; '+_inline(line[2:]),styles['bullet']));i+=1;continue
        paragraph.append(line);i+=1
    flush()
    if demo:
        story.insert(0,Paragraph('DEMONSTRATION ONLY — NOT ENGINE RESULTS',styles['h3']))
    def page_header(canvas,doc):
        canvas.saveState()
        w,h=A4
        canvas.setFont(bold,9);canvas.setFillColor(GREEN);canvas.drawString(47,h-38,'FIELDWISE')
        canvas.setFont(regular,7.5);canvas.setFillColor(MUTED);canvas.drawRightString(w-47,h-38,'FIELD ANALYSIS / TECHNICAL REPORT')
        canvas.setStrokeColor(RULE);canvas.line(47,h-46,w-47,h-46)
        canvas.line(47,43,w-47,43)
        canvas.setFont(regular,7.3);canvas.drawString(47,30,'Historical decision-support model - interpret with field validation')
        canvas.drawRightString(w-47,30,f'Page {doc.page}')
        canvas.restoreState()
    doc.build(story,onFirstPage=page_header,onLaterPages=page_header)
    return buffer.getvalue()
