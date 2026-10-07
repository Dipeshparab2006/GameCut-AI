from pathlib import Path
from docx import Document

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'output'/'report'/'GameCut_AI_Project_Report.docx'
doc=Document(str(path))
removed=0
captions={'System Architecture of GameCut AI','Level 1 Data Flow Diagram','Entity Relationship Diagram','Activity and Processing Flow','GameCut AI AI-Assisted Processing Pipeline'}
paras=list(doc.paragraphs)
for para in paras:
    has_drawing=bool(para._p.xpath('.//w:drawing') or para._p.xpath('.//pic:pic'))
    if has_drawing or para.text.strip() in captions:
        para._element.getparent().remove(para._element)
        removed+=1
out=ROOT/'output'/'report'/'GameCut_AI_Project_Report_Content_Only.docx'
doc.save(out)
print(f'{out} removed={removed}')
