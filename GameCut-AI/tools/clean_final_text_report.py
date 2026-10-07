from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / 'output' / 'report' / 'GameCut_AI_Project_Report_Detailed.txt'
out = ROOT / 'output' / 'report' / 'GameCut_AI_Project_Report_Final.txt'

text = src.read_text(encoding='utf-8')
remove_lines = {
    'DETAILED PROJECT CONTENT',
    'EXPANDED DETAILED MAIN REPORT',
    'TECHNICAL ANNEXURE - DETAILED IMPLEMENTATION NOTES',
    'END OF DETAILED PROJECT REPORT',
}
clean=[]
for line in text.splitlines():
    stripped=line.strip()
    if stripped in remove_lines:
        continue
    line=line.replace('DETAILED ', '').replace('Detailed ', '')
    line=line.replace('backend', 'server-side application').replace('Backend', 'Server-side application')
    line=line.replace('AI-generated', 'generated').replace('ai-generated', 'generated')
    line=line.replace('current project source and its supporting documentation', 'the implemented project and its documentation')
    clean.append(line)

out_text='\n'.join(clean)
while '\n\n\n\n' in out_text:
    out_text=out_text.replace('\n\n\n\n','\n\n\n')
out.write_text(out_text.strip()+'\n', encoding='utf-8')
print(out)
