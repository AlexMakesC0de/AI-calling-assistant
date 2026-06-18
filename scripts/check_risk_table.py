from docx import Document

doc = Document(r"D:\Downloads\Test Plan v1.1.docx")

# Table 39 (index 38) and Table 40 (index 39)
for tidx in [38, 39, 40]:
    if tidx < len(doc.tables):
        t = doc.tables[tidx]
        print("Table " + str(tidx + 1) + ":")
        print("  Rows: " + str(len(t.rows)) + ", Cols: " + str(len(t.columns)))
        for r_idx, row in enumerate(t.rows):
            cells = []
            for cell in row.cells:
                cells.append(cell.text.strip()[:40])
            print("  Row " + str(r_idx) + " (" + str(len(row.cells)) + " cells): " + " | ".join(cells))
        print()
