
"""Fill a Word (.docx) template using tokens that map to a JSON schema.

Usage:
  python generate_word.py --template TEMPLATE.docx --data data.json --out out.docx

Tokens are of the form {caller_information.properties.name} and will be
replaced by traversing the provided JSON using the dot-separated path.
"""

import argparse
import json
import os
import re
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph


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


# ---------------------------------------------------------------------------
# Image / attachment embedding (ISR-318)
# ---------------------------------------------------------------------------

# Raster image types we embed inline. Other attachment types (PDF, etc.) are
# only referenced by name here; full non-image handling is ISR-319.
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff"}

# Optional anchor an operator can place in the template to control where the
# attachments land. When absent, the section is appended at the end.
ATTACH_TOKEN = "{attachments}"


def _usable_width(doc):
	"""Printable page width in EMU = page width minus left/right margins."""
	try:
		section = doc.sections[0]
		return int(section.page_width - section.left_margin - section.right_margin)
	except Exception:
		return None


def _insert_paragraph_after(paragraph):
	"""Create and return a new empty paragraph immediately after `paragraph`."""
	new_p = OxmlElement("w:p")
	paragraph._p.addnext(new_p)
	return Paragraph(new_p, paragraph._parent)


def _collect_attachments(data, media_dir=None):
	"""Normalise data['attachments'] into a list of (path, label, is_image).

	Each entry may be a plain path string, or a dict with 'path'/'file' and an
	optional 'filename'. Relative paths are resolved against `media_dir`.
	"""
	items = []
	for entry in data.get("attachments") or []:
		if isinstance(entry, str):
			path, label = entry, os.path.basename(entry)
		elif isinstance(entry, dict):
			path = entry.get("path") or entry.get("file") or entry.get("filename") or ""
			label = entry.get("filename") or (os.path.basename(path) if path else "attachment")
		else:
			continue
		if not path:
			continue
		if media_dir and not os.path.isabs(path):
			path = os.path.join(media_dir, path)
		is_image = os.path.splitext(path)[1].lower() in IMAGE_EXTS
		items.append((path, label, is_image))
	return items


def _find_attachments_anchor(doc):
	"""Return the paragraph holding the {attachments} token, or None."""
	for paragraph in doc.paragraphs:
		if ATTACH_TOKEN in (paragraph.text or ""):
			return paragraph
	return None


def _embed_image(paragraph, img_path, usable_width):
	"""Add `img_path` to `paragraph`, scaled DOWN to page width if needed.

	Small images are never upscaled; larger ones are capped at the printable
	page width with the aspect ratio preserved.
	"""
	shape = paragraph.add_run().add_picture(img_path)
	if usable_width and shape.width and shape.width > usable_width:
		ratio = usable_width / shape.width
		shape.width = int(round(shape.width * ratio))
		shape.height = int(round(shape.height * ratio))
	return shape


def _render_attachment(paragraph, path, label, is_image, usable_width):
	"""Render one attachment: image inline, otherwise a text reference."""
	if is_image:
		if not os.path.isfile(path):
			paragraph.add_run(f"[Missing image attachment: {label}]")
			return
		try:
			_embed_image(paragraph, path, usable_width)
		except Exception:
			# A single bad image must not break the whole document.
			paragraph.add_run(f"[Could not embed image: {label}]")
	else:
		# Non-image attachments are referenced by name (ISR-319 formalises this).
		paragraph.add_run(f"Attachment (see media folder): {label}")


def _add_attachments_heading(paragraph):
	run = paragraph.add_run("Attachments")
	run.bold = True


def embed_attachments(doc, data, media_dir=None):
	"""Embed image attachments into the document; return the count of items.

	Each attachment goes in its own paragraph (giving spacing), with images
	scaled to fit the page width. If the template contains an {attachments}
	token the section is placed there; otherwise it is appended at the end.
	The document layout is otherwise untouched.
	"""
	items = _collect_attachments(data, media_dir)
	if not items:
		return 0

	usable_width = _usable_width(doc)
	anchor = _find_attachments_anchor(doc)

	if anchor is not None:
		anchor.text = ""  # drop the literal {attachments} token
		_add_attachments_heading(anchor)
		cursor = anchor
		for path, label, is_image in items:
			cursor = _insert_paragraph_after(cursor)
			_render_attachment(cursor, path, label, is_image, usable_width)
	else:
		_add_attachments_heading(doc.add_paragraph())
		for path, label, is_image in items:
			_render_attachment(doc.add_paragraph(), path, label, is_image, usable_width)

	return len(items)


def main():
	parser = argparse.ArgumentParser(description="Fill .docx template with JSON data tokens")
	parser.add_argument("--template", "-t", required=True, help="Path to the .docx template")
	parser.add_argument("--data", "-d", required=True, help="Path to the JSON data file")
	parser.add_argument("--out", "-o", required=True, help="Output .docx path")
	parser.add_argument(
		"--media-dir", "-m", default=None,
		help="Base directory for resolving relative attachment paths "
		"(default: the data file's directory)",
	)
	args = parser.parse_args()

	with open(args.data, "r", encoding="utf-8") as f:
		data = json.load(f)

	media_dir = args.media_dir or os.path.dirname(os.path.abspath(args.data))

	doc = Document(args.template)
	replace_tokens_in_doc(doc, data)
	embed_attachments(doc, data, media_dir)
	doc.save(args.out)


if __name__ == "__main__":
	main()
