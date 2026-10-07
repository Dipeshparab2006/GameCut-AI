from pathlib import Path
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph as RParagraph, Spacer, PageBreak, Table as RTable, TableStyle, Image, KeepTogether

ROOT=Path(__file__).resolve().parents[1]; docx_path=ROOT/'output'/'report'/'GameCut_AI_Project_Report_Content_Only.docx'; pdf_path=ROOT/'output'/'report'/'GameCut_AI_Project_Report_Content_Only.pdf'
NAVY=colors.HexColor('#17324D'); BLUE=colors.HexColor('#2F75B5'); TEAL=colors.HexColor('#2A9D8F')

def iter_blocks(parent):
    for child in parent.element.body.iterchildren():
        if child.tag.endswith('}p'): yield Paragraph(child,parent)
        elif child.tag.endswith('}tbl'): yield Table(child,parent)
def image_for(paragraph, doc):
    blips=paragraph._p.xpath('.//a:blip')
    if not blips: return None
    rid=blips[0].get(qn('r:embed')); part=doc.part.related_parts[rid]; name=Path(str(part.partname)).name
    out=ROOT/'output'/'report'/('rendered_image_'+name)
    out.write_bytes(part.blob); return out
def header_footer(c, d):
    c.saveState(); c.setFont('Helvetica',8); c.setFillColor(colors.HexColor('#5B6573')); c.drawCentredString(A4[0]/2, .42*inch, f'GameCut AI | Project Report 2025-26 | {d.page}'); c.restoreState()
def main():
    doc=Document(str(docx_path)); styles=getSampleStyleSheet()
    normal=ParagraphStyle('NormalX',parent=styles['BodyText'],fontName='Helvetica',fontSize=9.2,leading=12,spaceAfter=6,textColor=colors.HexColor('#232B34'))
    title=ParagraphStyle('TitleX',parent=normal,fontName='Helvetica-Bold',fontSize=27,leading=32,textColor=NAVY,alignment=TA_CENTER,spaceAfter=14)
    h1=ParagraphStyle('H1X',parent=normal,fontName='Helvetica-Bold',fontSize=17,leading=21,textColor=NAVY,spaceBefore=10,spaceAfter=8)
    h2=ParagraphStyle('H2X',parent=normal,fontName='Helvetica-Bold',fontSize=12.5,leading=16,textColor=NAVY,spaceBefore=7,spaceAfter=5)
    cap=ParagraphStyle('CapX',parent=normal,fontName='Helvetica-Oblique',fontSize=8.5,alignment=TA_CENTER,textColor=colors.HexColor('#5B6573'))
    story=[]
    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            txt=block.text.strip(); img=image_for(block,doc)
            if img:
                story += [Spacer(1,8),Image(str(img),width=6.25*inch,height=3.55*inch),Spacer(1,5)]
                continue
            if not txt:
                # detect explicit page break paragraphs
                if block._p.xpath('.//w:br[@w:type="page"]'): story.append(PageBreak())
                continue
            if block._p.xpath('.//w:br[@w:type="page"]'): story.append(PageBreak()); continue
            sty=normal
            if block.style and block.style.name=='Title': sty=title
            elif block.style and block.style.name.startswith('Heading 1'): sty=h1
            elif block.style and block.style.name.startswith('Heading 2'): sty=h2
            elif block.style and block.style.name=='Caption': sty=cap
            safe=txt.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br/>')
            story.append(RParagraph(safe,sty))
        else:
            data=[]
            for row in block.rows:
                data.append([RParagraph(c.text.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br/>'),normal) for c in row.cells])
            if data:
                t=RTable(data,repeatRows=1,hAlign='CENTER',colWidths=[6.3*inch/len(data[0])]*len(data[0]))
                t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,colors.HexColor('#B8C7D2')),('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
                story += [Spacer(1,5),t,Spacer(1,8)]
    pdf=SimpleDocTemplate(str(pdf_path),pagesize=A4,rightMargin=.72*inch,leftMargin=.72*inch,topMargin=.65*inch,bottomMargin=.62*inch,title='GameCut AI Project Report',author='Project Student')
    pdf.build(story,onFirstPage=header_footer,onLaterPages=header_footer); print(pdf_path)
if __name__=='__main__': main()
