
"""Fill a Word (.docx) template using tokens that map to a JSON schema.

Usage:
  python generate_word.py --template TEMPLATE.docx --data data.json --out out.docx

Tokens are of the form {caller_information.properties.name} and will be
replaced by traversing the provided JSON using the dot-separated path.
"""

import argparse
import json
import re
from typing import Any

from docx import Document


TOKEN_RE = re.compile(r"\{([^}]+)\}")


def get_value_from_path(data: Any, path: str) -> str:
	"""Traverse `data` by dot-separated `path`. Return empty string if missing."""
	parts = path.split(".")
	cur = data
	for p in parts:
		# Skip schema keywords that appear in JSON Schema (e.g. properties, items)
		if p in ("properties", "items"):
			continue
		# If current is a dict, prefer dict lookup
		if isinstance(cur, dict):
			if p in cur:
				cur = cur[p]
				continue
			# allow numeric lookup into dicts if keys are numeric strings
			if p.isdigit() and p in cur:
				cur = cur[p]
				continue
			return ""
		# If current is a list and p is an index
		if isinstance(cur, list):
			if p.isdigit():
				idx = int(p)
				if 0 <= idx < len(cur):
					cur = cur[idx]
					continue
				return ""
			# if non-numeric, cannot descend
			return ""
	if cur is None:
		return ""
	if isinstance(cur, (dict, list)):
		try:
			return json.dumps(cur, ensure_ascii=False)
		except Exception:
			return str(cur)
	return str(cur)


def replace_tokens_in_paragraph(paragraph, data):
	text = paragraph.text
	if not text:
		return
	def _repl(match):
		path = match.group(1).strip()
		return get_value_from_path(data, path)

	new_text = TOKEN_RE.sub(_repl, text)
	if new_text != text:
		paragraph.text = new_text


def replace_tokens_in_doc(doc: Document, data: Any):
	# Replace in top-level paragraphs
	for paragraph in doc.paragraphs:
		replace_tokens_in_paragraph(paragraph, data)

	# Replace in tables
	for table in doc.tables:
		for row in table.rows:
			for cell in row.cells:
				for paragraph in cell.paragraphs:
					replace_tokens_in_paragraph(paragraph, data)

	# Replace in headers and footers
	for section in doc.sections:
		header = section.header
		for paragraph in header.paragraphs:
			replace_tokens_in_paragraph(paragraph, data)
		footer = section.footer
		for paragraph in footer.paragraphs:
			replace_tokens_in_paragraph(paragraph, data)


def main():
	parser = argparse.ArgumentParser(description="Fill .docx template with JSON data tokens")
	parser.add_argument("--template", "-t", required=True, help="Path to the .docx template")
	parser.add_argument("--data", "-d", required=True, help="Path to the JSON data file")
	parser.add_argument("--out", "-o", required=True, help="Output .docx path")
	args = parser.parse_args()

	with open(args.data, "r", encoding="utf-8") as f:
		data = json.load(f)

	doc = Document(args.template)
	replace_tokens_in_doc(doc, data)
	doc.save(args.out)


if __name__ == "__main__":
	main()
