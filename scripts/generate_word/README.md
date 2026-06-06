# Generate Word

Fill a Microsoft Word (.docx) template using a JSON file that follows the `incident_form_schema.json` structure.

## Prerequisites

- Python 3.8+
- Install dependencies:

```bash
python -m pip install -r scripts/generate_word/requirements.txt
```

## Purpose

This script finds tokens in a `.docx` template of the form `{caller_information.properties.name}` and replaces them with values from a JSON file (for example, `scripts/generate_word/incident.json`). Tokens use dot-separated paths that correspond to the JSON structure; the resolver skips common JSON Schema keywords like `properties` and `items` so tokens that follow the schema structure map to actual data.

## Usage

```bash
python scripts/generate_word/generate_word.py --template TEMPLATE.docx --data DATA.json --out OUT.docx
```

Example:

```bash
python scripts/generate_word/generate_word.py --template "templates/Meldingsformulier Service V2 leeg.docx" --data scripts/generate_word/incident.json --out filled.docx
```

## Token rules

- Tokens must be wrapped in curly braces: `{...}`
- Use dot-separated paths to traverse the JSON (e.g. `{caller_information.properties.name}`).
- The resolver will:
  - Skip `properties` and `items` when traversing paths that follow a JSON Schema layout.
  - Support numeric indices for lists (e.g. `items.0.name`).
  - Serialize objects/arrays as JSON strings when used in a token.
  - Replace missing values with an empty string.

## Notes

- The script replaces tokens in paragraphs, table cells, headers and footers. It does not currently replace text inside Word shapes/textboxes; ask if you need that.
- If you need richer formatting or to preserve runs with different styles, consider extending the replacement logic to operate on runs rather than whole-paragraph text.

## Files

- `scripts/generate_word/generate_word.py` — token-replacer script
- `scripts/generate_word/incident.json` — example data for testing
- `scripts/generate_word/requirements.txt` — dependencies (`python-docx`)

## License

MIT-style personal use within this repository.
