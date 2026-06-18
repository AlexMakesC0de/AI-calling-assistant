from docx import Document
from docx.oxml.ns import qn

doc = Document(r"D:\Downloads\Test Plan v1.1.docx")

t39 = doc.tables[38]
# Check actual XML structure of first two rows
for r_idx in range(min(2, len(t39.rows))):
    tr = t39.rows[r_idx]._tr
    tcs = tr.findall(qn('w:tc'))
    print("Row " + str(r_idx) + ": " + str(len(tcs)) + " tc elements")
    for tc_idx, tc in enumerate(tcs):
        tcPr = tc.find(qn('w:tcPr'))
        gridSpan = None
        if tcPr is not None:
            gs = tcPr.find(qn('w:gridSpan'))
            if gs is not None:
                gridSpan = gs.get(qn('w:val'))
        p = tc.find(qn('w:p'))
        text = ""
        if p is not None:
            for r in p.findall(qn('w:r')):
                for t in r.findall(qn('w:t')):
                    if t.text:
                        text += t.text
        print("  tc" + str(tc_idx) + " gridSpan=" + str(gridSpan) + " text=" + text[:30])

# Try adding a row manually
print()
print("Attempting manual row add...")
row = t39.add_row()
print("New row cells: " + str(len(row.cells)))
tr = row._tr
tcs = tr.findall(qn('w:tc'))
print("New row tc elements: " + str(len(tcs)))
