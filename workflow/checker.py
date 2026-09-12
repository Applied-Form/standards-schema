"""Offline checks for the six supported Instrument HTML workflows.

This is a content/structure/render-evidence check, not a design-quality scorer.
It performs no filesystem reads, network requests or browser execution.
"""
import base64
import binascii
import hashlib
from html.parser import HTMLParser
import json
import math
import re
import unicodedata
import zlib


SCHEMA_VERSION = "0.2.0"
MAX_HTML_BYTES = 2_000_000
MAX_PLAN_BYTES = 500_000
MAX_EVIDENCE_BYTES = 3_500_000
MAX_NODES = 20_000
MAX_DEPTH = 128
MAX_FACTS = 300
MAX_FINDINGS = 1_000
TOLERANCE_PX = 1
LIMITATIONS = [
    "Supports the six Instrument HTML workflows declared by the exact support-manifest bytes.",
    "Visual quality, rhetorical effectiveness and full accessibility compliance are unassessed.",
    "Source visibility is conservative; CSS layout and clipping require current browser evidence.",
    "Render evidence is caller supplied and hash-bound, not an attestation of browser execution.",
    "Vertical document scrolling is permitted; required horizontal viewport fit is checked.",
]


def normalize_text(value):
    """Normalize Unicode composition and whitespace without changing symbols or signs."""
    return " ".join(unicodedata.normalize("NFC", value).split())


def _digest_plan(plan):
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                         allow_nan=False).encode("utf-8")
    if len(encoded) > MAX_PLAN_BYTES:
        raise ValueError("plan exceeds size limit")
    return hashlib.sha256(encoded).hexdigest()


def _string(value, name):
    if not isinstance(value, str) or not normalize_text(value):
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _expected_facts(plan):
    if not isinstance(plan, dict):
        raise ValueError("plan must be an object")
    if plan.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError("unsupported plan schemaVersion")
    facts = plan.get("facts")
    if not isinstance(facts, list) or not 1 <= len(facts) <= MAX_FACTS:
        raise ValueError("facts must be a bounded nonempty array")
    expected = {}
    for fact in facts:
        if not isinstance(fact, dict):
            raise ValueError("fact must be an object")
        identifier = _string(fact.get("id"), "fact id")
        if not re.fullmatch(r"[a-zA-Z0-9.]{1,120}", identifier) or identifier in expected:
            raise ValueError("duplicate or invalid plan fact id")
        expected[identifier] = _string(fact.get("text"), "fact text")
    return expected

class _Node:
    def __init__(self, tag, attrs=None, parent=None, position=None):
        self.tag, self.attrs, self.parent = tag, attrs or {}, parent
        self.children, self.position = [], position
        self.hidden = False


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
        "param", "source", "track", "wbr"}
NON_CONTENT = {"head", "title", "script", "style", "template", "noscript"}
FORBIDDEN = {"script", "iframe", "object", "embed", "base", "canvas", "img", "svg", "video", "audio",
             "a", "button", "input", "select", "textarea", "form", "option", "datalist", "output",
             "details", "summary", "dialog"}


def _inline_hidden(attrs):
    if "hidden" in attrs or attrs.get("aria-hidden", "").lower() == "true":
        return True
    style = attrs.get("style", "")
    return bool(re.search(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*(?:hidden|collapse)|"
                          r"content-visibility\s*:\s*hidden|opacity\s*:\s*0(?:\.0+)?(?:\s*!important)?\s*(?:;|$)|"
                          r"font-size\s*:\s*0(?:px|em|rem|%)?(?:\s*!important)?\s*(?:;|$))", style, re.I))


class _Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#document")
        self.stack, self.nodes, self.errors, self.unsafe = [self.root], [], [], []
        self.doctypes = 0

    def handle_decl(self, decl):
        if decl.lower() == "doctype html":
            self.doctypes += 1
        else:
            self.errors.append("unsupported document declaration")

    def handle_starttag(self, tag, attrs):
        if len(self.nodes) >= MAX_NODES or len(self.stack) >= MAX_DEPTH:
            raise ValueError("HTML node/depth limit exceeded")
        keys = [key for key, _ in attrs]
        if len(keys) != len(set(keys)):
            self.errors.append("duplicate HTML attributes")
        values = {key: value or "" for key, value in attrs}
        node = _Node(tag, values, self.stack[-1], self.getpos())
        node.hidden = node.parent.hidden or tag in NON_CONTENT or _inline_hidden(values)
        node.parent.children.append(node)
        self.nodes.append(node)
        if tag in FORBIDDEN:
            self.unsafe.append(f"unsupported active or visual element: {tag}")
        if any(key.startswith("on") for key in values):
            self.unsafe.append("event handler attributes")
        if any(key in values for key in ("title", "aria-label", "aria-description", "placeholder", "value", "alt",
                                         "contenteditable", "tabindex", "formaction")):
            self.unsafe.append("unsupported interactive or attribute-rendered text")
        if values.get("role", "").lower() in {"button", "link", "checkbox", "menuitem", "option", "radio",
                                                 "searchbox", "slider", "spinbutton", "switch", "tab", "textbox"}:
            self.unsafe.append("unsupported interactive role")
        if tag == "meta" and "http-equiv" in values:
            self.unsafe.append("http-equiv metadata")
        for key in ("src", "srcset", "poster", "data"):
            if values.get(key):
                self.unsafe.append(f"unsupported resource attribute: {tag}.{key}")
        if tag == "link" and values.get("href"):
            self.unsafe.append("external or separately loaded stylesheet/resource")
        if values.get("href", "").strip().lower().startswith(("javascript:", "data:", "vbscript:")):
            self.unsafe.append("active hyperlink target")
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            self.errors.append(f"closing tag for void element {tag}")
        elif self.stack[-1].tag == tag:
            self.stack.pop()
        else:
            self.errors.append(f"unbalanced closing tag {tag}")
            for index in range(len(self.stack) - 1, 0, -1):
                if self.stack[index].tag == tag:
                    del self.stack[index:]
                    break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _ancestor(node, tag):
    while node is not None:
        if node.tag == tag:
            return node
        node = node.parent
    return None


def _unit_span(node, name):
    return node.attrs.get(name, "1") == "1"


def _body_visible(node):
    return not node.hidden and _ancestor(node, "body") is not None


def _text(node, visible=True):
    if visible and node.hidden:
        return ""
    if node.tag == "br":
        return "\n"
    return "".join(child if isinstance(child, str) else _text(child, visible) for child in node.children)


def _css_problems(document):
    problems = []
    css = "\n".join(_text(node, False) if node.tag == "style" else node.attrs.get("style", "")
                    for node in document.nodes)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    if re.search(r"@import\b|(?:^|[;{])\s*content\s*:|"
                 r"(?:repeating-)?(?:linear|radial|conic)-gradient\s*\(", css, re.I):
        problems.append("CSS imports, generated text or gradients are unsupported")
    if re.search(r"@(?:-[a-z]+-)?keyframes\b|(?:^|[;{])\s*(?:-[a-z]+-)?(?:animation|transition|filter|"
                 r"backdrop-filter|mask(?:-image)?|mix-blend-mode|clip-path|transform|opacity|text-indent|"
                 r"box-shadow|"
                 r"(?:-webkit-)?text-fill-color|(?:-webkit-)?text-stroke(?:-width|-color)?|"
                 r"text-shadow|-webkit-text-security|"
                 r"z-index|pointer-events)\s*:|(?:^|[;{])\s*position\s*:\s*(?:absolute|fixed|sticky)\b|"
                 r"(?:^|[;{])\s*(?:display\s*:\s*none|visibility\s*:\s*(?:hidden|collapse)|"
                 r"font-size\s*:\s*0(?:px|em|rem|%)?)(?:\s*!important)?\s*(?:;|})", css, re.I):
        problems.append("dynamic, layered or visually hiding CSS is unsupported")
    for value in re.findall(r"url\(\s*['\"]?([^)'\"]+)['\"]?\s*\)", css, re.I):
        match = re.fullmatch(r"data:font/woff2;base64,([A-Za-z0-9+/=\s]+)", value.strip(), re.I)
        if not match:
            problems.append("only embedded WOFF2 font URLs are supported")
            continue
        try:
            font = base64.b64decode(re.sub(r"\s", "", match.group(1)), validate=True)
            if not font.startswith(b"wOF2"):
                problems.append("embedded font is not WOFF2")
        except ValueError:
            problems.append("invalid embedded font encoding")
    return problems


def _semantics(document, markers, expected, plan, add):
    """Check source-level relationships declared for the selected move."""
    order = {id(node): index for index, node in enumerate(document.nodes)}

    def one(identifier):
        nodes = markers.get(identifier, [])
        return nodes[0] if len(nodes) == 1 else None

    def record(identifier, passed, expected_value, observed):
        add("move.semantics", "info" if passed else "error", "pass" if passed else "fail",
            identifier, expected_value, observed, not passed)

    title = one("title")
    record("title", bool(title and _ancestor(title, "h1") is not None),
           "the unique title fact in a level-one heading",
           "present" if title else "missing or duplicated")
    kind = plan["content"]["kind"]
    data = plan["content"]["data"]

    if kind == "datum":
        label, value = one("datum.label"), one("datum.value")
        sections = [node for node in document.nodes if node.tag == "section" and _body_visible(node)]
        passed = bool(len(sections) == 1 and label and value
                      and _ancestor(label, "section") is sections[0]
                      and _ancestor(value, "section") is sections[0]
                      and order[id(label)] < order[id(value)])
        record("datum.label-value", passed, "label and primary value in one Datum section",
               {"sectionCount": len(sections), "label": bool(label), "value": bool(value),
                "sameOrderedSection": passed})
    elif kind == "matrix":
        tables = [node for node in document.nodes if node.tag == "table" and _body_visible(node)]
        table = tables[0] if len(tables) == 1 else None
        columns = [one(f"matrix.columns.{index}") for index in range(len(data["columns"]))]
        headers = ([node for node in document.nodes if node.tag == "th"
                    and _ancestor(node, "thead") is not None
                    and _ancestor(node, "table") is table and _body_visible(node)] if table else [])
        column_ok = bool(table and len(headers) == len(columns) + 1 and all(columns)
                         and columns == headers[1:]
                         and all(node.attrs.get("scope") == "col"
                                 and _unit_span(node, "colspan") and _unit_span(node, "rowspan")
                                 for node in columns))
        record("matrix.column-headers", column_ok,
               "one visible Matrix table with ordered scope=col fact headers",
               {"tableCount": len(tables), "headerCount": len(headers)})
        rows = ([node for node in document.nodes if node.tag == "tr"
                 and _ancestor(node, "tbody") is not None
                 and _ancestor(node, "table") is table and _body_visible(node)] if table else [])
        row_headers, grid_ok = [], bool(table and len(rows) == len(data["rows"]))
        for row_index, row in enumerate(data["rows"]):
            header = one(f"matrix.rows.{row_index}.label")
            row_node = rows[row_index] if row_index < len(rows) else None
            cells = ([child for child in row_node.children
                      if isinstance(child, _Node) and child.tag in ("th", "td")]
                     if row_node else [])
            row_headers.append(header)
            row_ok = bool(len(cells) == len(data["columns"]) + 1 and header is cells[0]
                          and header.tag == "th" and header.attrs.get("scope") == "row"
                          and all(_unit_span(cell, "colspan") and _unit_span(cell, "rowspan")
                                  for cell in cells))
            grid_ok = grid_ok and row_ok
            for column_index in range(len(row["values"])):
                cell = one(f"matrix.rows.{row_index}.values.{column_index}")
                grid_ok = grid_ok and bool(row_ok and cell is cells[column_index + 1]
                                           and cell.tag == "td")
        headers_ok = bool(table and len(rows) == len(data["rows"]) and all(row_headers)
                          and all(node.attrs.get("scope") == "row" for node in row_headers))
        emphasized = [node for node in document.nodes
                      if node.attrs.get("data-matrix-emphasis") == "true"]
        if "emphasis" in data:
            row_index, column_index = data["emphasis"]
            planned = one(f"matrix.rows.{row_index}.values.{column_index}")
            grid_ok = grid_ok and emphasized == [planned]
        else:
            grid_ok = grid_ok and not emphasized
        record("matrix.row-headers", headers_ok, "one scope=row fact header per Matrix row",
               {"expected": len(data["rows"]), "observed": sum(node is not None for node in row_headers)})
        record("matrix.grid", bool(grid_ok), "every Matrix value in its declared row and column grid",
               {"rows": len(data["rows"]), "columns": len(data["columns"])})
    elif kind == "bandStatement":
        statement = one("bandStatement.statement")
        sections = [node for node in document.nodes if node.tag == "section" and _body_visible(node)]
        passed = bool(len(sections) == 1 and statement and statement.tag == "p"
                      and statement.parent and statement.parent.tag == "div"
                      and statement.parent.parent is sections[0])
        record("bandStatement.statement", passed,
               "the statement fact in paragraph semantics inside one Band statement section",
               {"sectionCount": len(sections), "present": bool(statement),
                "tag": statement.tag if statement else None})
    elif kind == "series":
        lists = [node for node in document.nodes if node.tag == "ol" and _body_visible(node)]
        period_nodes, display_nodes = [], []
        association_ok = len(lists) == 1
        for index in range(len(data["periods"])):
            period = one(f"series.periods.{index}.period")
            display = one(f"series.periods.{index}.display")
            period_nodes.append(period); display_nodes.append(display)
            association_ok = association_ok and bool(period and display
                                                       and _ancestor(period, "li") is _ancestor(display, "li")
                                                       and _ancestor(period, "ol") is lists[0])
        items = ([child for child in lists[0].children
                  if isinstance(child, _Node) and child.tag == "li"] if len(lists) == 1 else [])
        period_items = [_ancestor(node, "li") if node else None for node in period_nodes]
        positions = [order[id(item)] for item in period_items if item is not None]
        label = one("series.label")
        labelled = bool(label and label.attrs.get("id")
                        and len(lists) == 1
                        and lists[0].attrs.get("aria-labelledby") == label.attrs["id"])
        order_ok = bool(len(items) == len(data["periods"]) and all(period_nodes)
                        and period_items == items and labelled
                        and len(set(positions)) == len(positions) and positions == sorted(positions))
        record("series.period-order", order_ok,
               "period facts in one ordered list and in plan order",
               {"expected": len(data["periods"]), "observed": len(positions)})
        if data["emphasiseLast"]:
            current = one("series.current")
            association_ok = association_ok and bool(items and current
                                                       and _ancestor(current, "li") is items[-1])
        record("series.value-association", bool(association_ok),
               "each visible period and display value in the same list item, with current on the last",
               bool(association_ok))
    elif kind == "schedule":
        tables = [node for node in document.nodes if node.tag == "table" and _body_visible(node)]
        table = tables[0] if len(tables) == 1 else None
        label = one("schedule.label")
        named = bool(table and label and label.tag == "caption" and label.parent is table
                     and not table.attrs.get("aria-label") and not table.attrs.get("aria-labelledby"))
        record("schedule.named-table", named, "one table named by its checked Schedule caption",
               {"tableCount": len(tables), "caption": bool(label)})
        headers = ([node for node in document.nodes
                    if node.tag == "th" and _ancestor(node, "thead") is not None
                    and _ancestor(node, "table") is table and _body_visible(node)]
                   if table else [])
        column_nodes = [one(f"schedule.columns.{field}")
                        for field in ("ref", "description", "duration", "amount")]
        columns_ok = bool(table and len(headers) == 4 and all(column_nodes)
                          and all(node.attrs.get("scope") == "col"
                                  and _unit_span(node, "colspan") and _unit_span(node, "rowspan")
                                  for node in headers)
                          and column_nodes == headers)
        record("schedule.column-headers", columns_ok,
               "four ordered unspanned scope=col fact headers", bool(columns_ok))
        rows = ([node for node in document.nodes
                 if node.tag == "tr" and _ancestor(node, "tbody") is not None
                 and _ancestor(node, "table") is table and _body_visible(node)]
                if table else [])
        rows_ok = bool(table and len(rows) == len(data["lines"]))
        numeric_ok = rows_ok
        for index, line in enumerate(data["lines"]):
            row = rows[index] if index < len(rows) else None
            cells = ([child for child in row.children
                      if isinstance(child, _Node) and child.tag in ("th", "td")]
                     if row else [])
            structure_ok = bool(len(cells) == 4 and cells[0].tag == "th"
                                and cells[0].attrs.get("scope") == "row"
                                and all(_unit_span(cell, "colspan") and _unit_span(cell, "rowspan")
                                        for cell in cells))
            rows_ok = rows_ok and structure_ok
            ref = one(f"schedule.lines.{index}.ref")
            duration = one(f"schedule.lines.{index}.duration")
            amount = one(f"schedule.lines.{index}.amount")
            rows_ok = rows_ok and bool(structure_ok and ref is cells[0])
            numeric_ok = numeric_ok and bool(structure_ok and duration is cells[2]
                                             and amount is cells[3])
            for field, column in (("description", 1), ("standard", 1)):
                identifier = f"schedule.lines.{index}.{field}"
                if identifier in expected:
                    node = one(identifier)
                    rows_ok = rows_ok and bool(structure_ok and node
                                               and _ancestor(node, cells[column].tag) is cells[column])
        record("schedule.row-headers", bool(rows_ok),
               "one four-cell row with a scope=row fact header and associated text per line",
               {"expectedRows": len(data["lines"]), "observedRows": len(rows),
                "passed": bool(rows_ok)})
        record("schedule.numeric-order", bool(numeric_ok),
               "duration and amount facts occupy columns three and four in every line",
               bool(numeric_ok))
        footers = [node for node in document.nodes if node.tag == "tfoot" and node.parent is table]
        if "total" in data:
            total = [one(f"schedule.total.{field}") for field in ("label", "duration", "amount")]
            footer_rows = ([child for child in footers[0].children
                            if isinstance(child, _Node) and child.tag == "tr"]
                           if len(footers) == 1 and _body_visible(footers[0]) else [])
            footer_cells = ([child for child in footer_rows[0].children
                             if isinstance(child, _Node) and child.tag in ("th", "td")]
                            if len(footer_rows) == 1 else [])
            footer_ok = bool(len(footer_cells) == 3 and footer_cells[0].tag == "th"
                             and footer_cells[0].attrs.get("scope") == "row"
                             and footer_cells[0].attrs.get("colspan") == "2"
                             and _unit_span(footer_cells[0], "rowspan")
                             and all(cell.tag == "td" and _unit_span(cell, "colspan")
                                     and _unit_span(cell, "rowspan") for cell in footer_cells[1:])
                             and all(total)
                             and total == footer_cells)
        else:
            footer_ok = not footers
        record("schedule.footer", footer_ok,
               "one exact associated footer row for a declared total, otherwise no footer",
               {"declared": "total" in data, "footerCount": len(footers)})
    elif kind == "runningIndex":
        navs = [node for node in document.nodes if node.tag == "nav" and _body_visible(node)]
        lists = [node for node in document.nodes if node.tag == "ol" and _body_visible(node)]
        sections = [one(f"runningIndex.sections.{index}") for index in range(len(data["sections"]))]
        numbers = [one(f"runningIndex.numbers.{index}") for index in range(len(data["sections"]))]
        items = ([child for child in lists[0].children
                  if isinstance(child, _Node) and child.tag == "li"] if len(lists) == 1 else [])
        section_items = [_ancestor(node, "li") if node else None for node in sections]
        positions = [order[id(item)] for item in section_items if item]
        document_label = one("runningIndex.document")
        labelled = bool(len(navs) == 1 and document_label and document_label.attrs.get("id")
                        and navs[0].attrs.get("aria-labelledby") == document_label.attrs["id"]
                        and not navs[0].attrs.get("aria-label"))
        order_ok = bool(labelled and len(lists) == 1 and _ancestor(lists[0], "nav") is navs[0]
                        and len(items) == len(data["sections"]) and section_items == items
                        and all(sections) and all(numbers)
                        and all(_ancestor(numbers[index], "li") is items[index]
                                and order[id(numbers[index])] < order[id(sections[index])]
                                for index in range(len(items)))
                        and len(set(positions)) == len(positions) and positions == sorted(positions))
        record("runningIndex.section-order", order_ok,
               "section facts in one labelled navigation ordered list and in plan order",
               {"expected": len(data["sections"]), "observed": len(positions)})
        current = data["current"] - 1
        current_nodes = [node for node in document.nodes if node.attrs.get("aria-current") == "step"
                         and _body_visible(node)]
        expected_li = _ancestor(sections[current], "li") if sections[current] else None
        current_ok = len(current_nodes) == 1 and current_nodes[0] is expected_li
        record("runningIndex.current-section", current_ok,
               "exactly the planned current section marked aria-current=step",
               {"plannedIndex": data["current"], "currentCount": len(current_nodes)})


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _screenshot_problems(viewport):
    screenshot = viewport.get("screenshot")
    if not isinstance(screenshot, dict):
        return ["screenshot observation missing"]
    try:
        encoded = screenshot["dataBase64"]
        if not isinstance(encoded, str) or len(encoded) > 1_500_000:
            raise ValueError("encoded screenshot is missing or exceeds its limit")
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) < 45 or raw[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("screenshot is not a complete PNG")
        position, chunks, idat_payloads, width, height = 8, [], [], None, None
        while position < len(raw):
            if position + 12 > len(raw):
                raise ValueError("PNG has a truncated chunk")
            length = int.from_bytes(raw[position:position + 4], "big")
            chunk_type = raw[position + 4:position + 8]
            end = position + 12 + length
            if length > 1_500_000 or end > len(raw):
                raise ValueError("PNG chunk is truncated or exceeds its limit")
            payload = raw[position + 8:position + 8 + length]
            recorded_crc = int.from_bytes(raw[position + 8 + length:end], "big")
            if zlib.crc32(chunk_type + payload) & 0xffffffff != recorded_crc:
                raise ValueError("PNG chunk CRC is invalid")
            chunks.append(chunk_type)
            if len(chunks) == 1:
                if chunk_type != b"IHDR" or length != 13:
                    raise ValueError("PNG must start with one IHDR chunk")
                width, height = int.from_bytes(payload[:4], "big"), int.from_bytes(payload[4:8], "big")
                if payload[8:] != b"\x08\x02\x00\x00\x00":
                    raise ValueError("PNG must be non-interlaced 8-bit RGB")
            if chunk_type == b"IDAT":
                idat_payloads.append(payload)
            if chunk_type == b"IEND":
                if length != 0 or end != len(raw):
                    raise ValueError("PNG IEND is invalid or not final")
                position = end
                break
            position = end
        if chunks.count(b"IHDR") != 1 or b"IDAT" not in chunks or not chunks or chunks[-1] != b"IEND":
            raise ValueError("PNG is missing required image chunks")
        if height > 20_000 or width * height > 40_000_000:
            raise ValueError("PNG dimensions exceed the renderer capture limits")
        row_bytes = 1 + width * 3
        rows, pending = 0, b""

        def consume(output):
            nonlocal rows, pending
            pending += output
            while len(pending) >= row_bytes:
                row, pending = pending[:row_bytes], pending[row_bytes:]
                if row[0] > 4:
                    raise ValueError("PNG scanline has an invalid filter")
                rows += 1
                if rows > height:
                    raise ValueError("PNG contains excess decoded scanlines")

        decoder = zlib.decompressobj()
        for compressed in idat_payloads:
            remainder = compressed
            while remainder:
                consume(decoder.decompress(remainder, 1_000_000))
                remainder = decoder.unconsumed_tail
        consume(decoder.flush())
        if not decoder.eof or decoder.unused_data or pending or rows != height:
            raise ValueError("PNG image data is not a complete RGB scanline stream")
        if hashlib.sha256(raw).hexdigest() != screenshot.get("sha256"):
            raise ValueError("screenshot SHA-256 does not match embedded bytes")
        document = viewport["document"]
        expected_heights = {int(document["clientHeight"]),
                            int(max(document["clientHeight"], document["scrollHeight"]))}
        if width != viewport["width"] or height not in expected_heights:
            raise ValueError("PNG dimensions differ from the rendered viewport/document")
    except (KeyError, TypeError, ValueError, binascii.Error, OverflowError, zlib.error) as error:
        return [str(error)]
    return []


def _render_checks(plan, expected, evidence, plan_hash, artifact_hash, add):
    declared = {(viewport["width"], viewport["height"]) for viewport in plan["artifact"]["viewports"]}
    binding_problem = None
    if not isinstance(evidence, dict):
        binding_problem = "render evidence missing"
    else:
        try:
            encoded_evidence = json.dumps(evidence, ensure_ascii=False, allow_nan=False,
                                          separators=(",", ":")).encode("utf-8")
            if len(encoded_evidence) > MAX_EVIDENCE_BYTES:
                raise ValueError(f"render evidence exceeds {MAX_EVIDENCE_BYTES} bytes")
            from .schema import load_schema, validate
            validate(evidence, load_schema("render-evidence"))
        except (TypeError, ValueError, RecursionError, UnicodeError) as error:
            binding_problem = f"render evidence does not match its schema: {error}"
        if binding_problem is None and (evidence.get("planSha256") != plan_hash
                                        or evidence.get("artifactSha256") != artifact_hash):
            binding_problem = "render evidence is stale or has mismatched hashes"
        if binding_problem is None:
            observed_renderer = evidence["renderer"]
            pinned = plan["renderer"]
            if any(observed_renderer.get(key) != value for key, value in pinned.items()):
                binding_problem = "rendered source, assets or runtime lock differ from the pinned renderer"
        if binding_problem is None:
            sizes = [(item["width"], item["height"]) for item in evidence["viewports"]]
            if len(sizes) != len(declared) or set(sizes) != declared:
                binding_problem = "render viewport declarations differ from the plan"
    add("render.binding", "warning" if binding_problem else "info", "unknown" if binding_problem else "pass",
        "render_evidence", {"planSha256": plan_hash, "artifactSha256": artifact_hash}, binding_problem, False)
    if binding_problem:
        for rule, expected_value in (("render.viewport_fit", "fresh viewport metrics"),
                                     ("render.facts", "fresh visible fact observations"),
                                     ("render.semantics", "fresh semantic observations"),
                                     ("instrument.invariant_band", "fresh invariant-band observations"),
                                     ("render.screenshot", "fresh embedded PNG evidence")):
            add(rule, "warning", "unknown", "render_evidence", expected_value,
                "unavailable until render.binding passes", False)
        return
    for viewport in evidence["viewports"]:
        location = f"viewport:{viewport['width']}x{viewport['height']}"
        document = viewport["document"]
        elements, errors, blocked = (viewport[name] for name in ("overflowingElements", "pageErrors", "blockedRequests"))
        client, scroll = document.get("clientWidth"), document.get("scrollWidth")
        metrics = all(_finite(document.get(key)) and document[key] > 0
                      for key in ("clientWidth", "clientHeight", "scrollWidth", "scrollHeight"))
        metrics = metrics and _finite(viewport.get("bodyTextLength")) and viewport["bodyTextLength"] > 0
        failures = []
        if client != viewport["width"] or document.get("clientHeight") != viewport["height"]:
            failures.append("browser client dimensions differ from the declared viewport")
        if (_finite(scroll) and scroll > viewport["width"] + TOLERANCE_PX
                or _finite(scroll) and _finite(client) and scroll > client + TOLERANCE_PX
                or elements):
            failures.append("horizontal overflow")
        if errors:
            failures.append("browser page errors")
        if blocked:
            failures.append("blocked resource requests")
        if viewport.get("bodyTextLength") == 0:
            failures.append("empty rendered body")
        status = "fail" if failures else "pass" if metrics else "unknown"
        add("render.viewport_fit", "error" if failures else "info", status, location,
            "horizontal fit, readable body and no browser/resource errors", failures or document, bool(failures))
        grouped = {}
        for fact in viewport["facts"]:
            grouped.setdefault(fact["id"], []).append(fact)
        fact_problems = 0
        for identifier, wanted in expected.items():
            items = grouped.get(identifier, [])
            if len(items) != 1:
                fact_problems += 1
                add("render.facts", "critical", "fail", f"{location}/{identifier}", "one rendered marker", len(items), True)
                continue
            item = items[0]
            bounds = item["bounds"]
            wrong = (not item["visible"] or item["clipped"] or item["occluded"]
                     or item["contrastRatio"] < 4.5
                     or normalize_text(item["text"]) != normalize_text(wanted)
                     or bounds["width"] <= 0 or bounds["height"] <= 0
                     or identifier.startswith("schedule.columns.")
                     and not 1 <= item["lineCount"] <= 2)
            if wrong:
                fact_problems += 1
                add("render.facts", "critical", "fail", f"{location}/{identifier}", wanted,
                    {key: item[key] for key in ("text", "visible", "clipped", "occluded", "contrastRatio", "lineCount", "bounds")}, True)
        invented = sorted(set(grouped) - set(expected))
        if invented:
            fact_problems += len(invented)
            add("render.facts", "critical", "fail", location, "only approved fact markers", invented, True)
        if fact_problems == 0:
            add("render.facts", "info", "pass", location,
                f"{len(expected)} exact, visible, unclipped and unobscured facts", len(viewport["facts"]), False)
        invented_text = [normalize_text(value) for value in viewport["unmarkedText"] if normalize_text(value)]
        add("facts.approved_text", "critical" if invented_text else "info", "fail" if invented_text else "pass",
            location, "no unapproved visible text", invented_text, bool(invented_text))
        semantics = viewport["semanticChecks"]
        relationships = semantics["relationships"]
        observed_ids = [item["id"] for item in relationships]
        required_ids = plan["requiredRelationships"]
        wrong = []
        if semantics["move"] != plan["move"]:
            wrong.append("semantic move differs from the plan")
        if not semantics["oneVisibleH1"]:
            wrong.append("expected exactly one visible level-one heading")
        if len(observed_ids) != len(set(observed_ids)):
            wrong.append("relationship identifiers are duplicated")
        missing = sorted(set(required_ids) - set(observed_ids))
        unexpected = sorted(set(observed_ids) - set(required_ids))
        failed = sorted(item["id"] for item in relationships if not item["passed"])
        if missing: wrong.append({"missingRelationships": missing})
        if unexpected: wrong.append({"unexpectedRelationships": unexpected})
        if failed: wrong.append({"failedRelationships": failed})
        expected_semantics = {"move": plan["move"], "oneVisibleH1": True,
                              "relationships": [{"id": item, "passed": True}
                                                for item in required_ids]}
        add("render.semantics", "error" if wrong else "info", "fail" if wrong else "pass",
            location, expected_semantics, wrong or semantics, bool(wrong))
        band = viewport["invariantBand"]
        band_bounds = band["bounds"]
        band_problems = []
        if band["count"] != 1:
            band_problems.append("expected exactly one invariant band")
        if not band["containsTitle"]:
            band_problems.append("the unique title marker is not inside the invariant band")
        if not isinstance(band_bounds, dict):
            band_problems.append("invariant-band bounds are unavailable")
        else:
            if abs(band_bounds["x"]) > TOLERANCE_PX:
                band_problems.append("invariant band does not begin at the viewport edge")
            if abs(band_bounds["y"]) > TOLERANCE_PX:
                band_problems.append("invariant band is not at the top of the artifact")
            if abs(band_bounds["width"] - document["clientWidth"]) > TOLERANCE_PX:
                band_problems.append("invariant band is not full measure")
            if abs(band_bounds["height"] - 32) > TOLERANCE_PX:
                band_problems.append("invariant band is not four 8px base units deep")
            title_items = grouped.get("title", [])
            if len(title_items) == 1:
                title_bounds = title_items[0]["bounds"]
                if (title_bounds["x"] < band_bounds["x"] - TOLERANCE_PX
                        or title_bounds["y"] < band_bounds["y"] - TOLERANCE_PX
                        or title_bounds["x"] + title_bounds["width"]
                            > band_bounds["x"] + band_bounds["width"] + TOLERANCE_PX
                        or title_bounds["y"] + title_bounds["height"]
                            > band_bounds["y"] + band_bounds["height"] + TOLERANCE_PX):
                    band_problems.append("title bounds are outside the invariant band")
        colours = {
            "backgroundColor": re.sub(r"\s+", "", (band["backgroundColor"] or "").lower()),
            "titleColor": re.sub(r"\s+", "", (band["titleColor"] or "").lower()),
        }
        if colours["backgroundColor"] != "rgb(17,17,17)":
            band_problems.append("invariant band does not use the pinned ink colour")
        if colours["titleColor"] != "rgb(255,255,255)":
            band_problems.append("invariant-band title is not 100% white")
        border_widths = band["borderWidths"]
        if not isinstance(border_widths, dict):
            band_problems.append("invariant-band border observations are unavailable")
        elif any(width > 0 for width in border_widths.values()):
            band_problems.append("invariant band must be an uninterrupted solid fill without a border")
        expected_band = {"count": 1, "containsTitle": True, "x": 0,
                         "width": document["clientWidth"], "height": 32,
                         "backgroundColor": "rgb(17, 17, 17)",
                         "titleColor": "rgb(255, 255, 255)",
                         "borderWidths": {"top": 0, "right": 0, "bottom": 0, "left": 0}}
        add("instrument.invariant_band", "error" if band_problems else "info",
            "fail" if band_problems else "pass", location, expected_band,
            band_problems or band, bool(band_problems))
        screenshot_problems = _screenshot_problems(viewport)
        add("render.screenshot", "error" if screenshot_problems else "info",
            "fail" if screenshot_problems else "pass", location,
            "hash-matched embedded PNG with declared width and captured height",
            screenshot_problems or {"file": viewport["screenshot"]["file"],
                                    "sha256": viewport["screenshot"]["sha256"]},
            bool(screenshot_problems))


def check_artifact(plan: dict, html: str, render_evidence: dict | None = None) -> dict:
    """Return a bounded content/structure report; missing render evidence is unknown."""
    report = {"schemaVersion": SCHEMA_VERSION, "planSha256": None, "artifactSha256": None,
              "status": "unknown", "summary": {}, "findings": [], "limitations": list(LIMITATIONS)}
    dropped_findings = 0

    def bounded(value, depth=0):
        if depth > 6:
            return "[depth limit]"
        if isinstance(value, str):
            return value[:5000]
        if isinstance(value, list):
            items = [bounded(item, depth + 1) for item in value[:100]]
            if len(value) > 100:
                items.append(f"[{len(value) - 100} more items omitted]")
            return items
        if isinstance(value, dict):
            items = list(value.items())[:100]
            result = {str(key)[:300]: bounded(item, depth + 1) for key, item in items}
            if len(value) > 100:
                result["_omitted"] = len(value) - 100
            return result
        return value

    def classification(rule, status, safe_model_repair):
        if (rule in ("render.binding", "render.screenshot")
                or status == "unknown" and rule.startswith(("render.", "instrument."))):
            return "renderer-or-configuration"
        if status == "fail" and safe_model_repair:
            return "safe-model-repair"
        if rule.startswith("human."):
            return "human-decision"
        return "non-repairable"

    def add(rule, severity, status, location, expected, observed, safe_model_repair):
        nonlocal dropped_findings
        if len(report["findings"]) >= MAX_FINDINGS - 1:
            dropped_findings += 1
            return
        clean_location = normalize_text(str(location))[:300] or "artifact"
        report["findings"].append({"ruleId": rule, "severity": severity, "status": status,
                                   "location": clean_location, "expected": bounded(expected),
                                   "observed": bounded(observed),
                                   "classification": classification(
                                       rule, status, safe_model_repair)})

    def finish():
        if dropped_findings:
            report["findings"].append({"ruleId": "report.bounded", "severity": "critical",
                                       "status": "fail", "location": "report",
                                       "expected": f"fewer than {MAX_FINDINGS} findings",
                                       "observed": {"omittedFindings": dropped_findings},
                                       "classification": "non-repairable"})
        statuses = [finding["status"] for finding in report["findings"]]
        report["status"] = "fail" if "fail" in statuses else "unknown" if "unknown" in statuses else "pass"
        report["summary"] = {"total": len(statuses),
                             "pass": statuses.count("pass"), "fail": statuses.count("fail"),
                             "unknown": statuses.count("unknown"),
                             "critical": sum(finding["severity"] == "critical" for finding in report["findings"]),
                             "error": sum(finding["severity"] == "error" for finding in report["findings"]),
                             "warning": sum(finding["severity"] == "warning" for finding in report["findings"])}
        return report

    try:
        # The public plan schema and source-code identity are part of the
        # contract. Direct Python callers receive the same validation as MCP.
        from .engine import validate_plan
        validate_plan(plan)
        report["planSha256"] = _digest_plan(plan)
        expected = _expected_facts(plan)
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        add("plan.valid", "critical", "fail", "plan", "supported valid workflow 0.2 plan", str(error), False)
        return finish()
    add("plan.valid", "info", "pass", "plan",
        "content, facts and binding agree with the support manifest", True, False)
    if not isinstance(html, str) or len(html) > MAX_HTML_BYTES:
        add("html.structure", "critical", "fail", "artifact", "bounded HTML string", "invalid type or size limit exceeded", False)
        return finish()
    try:
        encoded = html.encode("utf-8")
    except UnicodeError:
        add("html.structure", "critical", "fail", "artifact", "UTF-8 HTML", "invalid Unicode", False)
        return finish()
    report["artifactSha256"] = hashlib.sha256(encoded).hexdigest()
    if len(encoded) > MAX_HTML_BYTES:
        add("html.structure", "critical", "fail", "artifact", f"at most {MAX_HTML_BYTES} bytes", len(encoded), False)
        return finish()
    document = _Document()
    try:
        document.feed(html)
        document.close()
    except (ValueError, RecursionError) as error:
        add("html.structure", "critical", "fail", "artifact", "parseable bounded HTML", str(error), False)
        return finish()
    counts = {tag: sum(node.tag == tag for node in document.nodes) for tag in ("html", "head", "body")}
    structure = list(document.errors)
    if document.doctypes != 1 or any(count != 1 for count in counts.values()):
        structure.append("one HTML doctype, html, head and body required")
    if len(document.stack) != 1:
        structure.append("unclosed HTML elements")
    ids = [node.attrs["id"] for node in document.nodes if node.attrs.get("id")]
    if len(ids) != len(set(ids)):
        structure.append("HTML id values must be unique")
    add("html.structure", "error" if structure else "info", "fail" if structure else "pass", "artifact",
        "complete, balanced HTML document", structure, bool(structure))
    unsafe = sorted(set(document.unsafe + _css_problems(document)))
    add("html.self_contained", "error" if unsafe else "info", "fail" if unsafe else "pass", "artifact",
        "static self-contained HTML", unsafe, bool(unsafe))
    marker_nodes = [node for node in document.nodes if "data-std-fact" in node.attrs]
    if len(marker_nodes) > MAX_FACTS:
        add("facts.unique", "critical", "fail", "artifact", f"at most {MAX_FACTS} fact markers",
            len(marker_nodes), False)
        return finish()
    invalid_marker_ids = [node.attrs["data-std-fact"] for node in marker_nodes
                          if not re.fullmatch(r"[a-zA-Z0-9.]{1,120}", node.attrs["data-std-fact"])]
    if invalid_marker_ids:
        add("facts.unique", "critical", "fail", "artifact", "bounded fact-marker identifiers",
            invalid_marker_ids, True)
    markers = {}
    for node in document.nodes:
        if "data-std-fact" in node.attrs:
            identifier = node.attrs["data-std-fact"]
            markers.setdefault(identifier, []).append(node)
            parent = node.parent
            while parent is not None:
                if "data-std-fact" in parent.attrs:
                    add("facts.unique", "critical", "fail", identifier, "non-nested fact markers", "nested marker", True)
                    break
                parent = parent.parent
    unique_problems = 0
    exact_problems = 0
    unassessed_exact = 0
    for identifier, wanted in expected.items():
        nodes = markers.get(identifier, [])
        if len(nodes) != 1:
            unique_problems += 1
            unassessed_exact += 1
            add("facts.unique", "critical", "fail", identifier, "one marker", len(nodes), True)
        if len(nodes) == 1:
            node = nodes[0]
            actual = normalize_text(_text(node)) if _body_visible(node) else ""
            matches = actual == normalize_text(wanted)
            if not matches:
                exact_problems += 1
                add("facts.exact", "critical", "fail", identifier, wanted, actual, True)
    if unique_problems == 0 and not invalid_marker_ids:
        add("facts.unique", "info", "pass", "artifact", f"{len(expected)} unique fact markers", len(markers), False)
    if exact_problems == 0 and unassessed_exact == 0:
        add("facts.exact", "info", "pass", "artifact", f"{len(expected)} exact facts", len(expected), False)
    elif unassessed_exact:
        add("facts.exact", "warning", "unknown", "artifact", "one marker before exact comparison",
            {"unassessedFacts": unassessed_exact}, False)
    for identifier in sorted(set(markers) - set(expected)):
        add("facts.approved_text", "critical", "fail", identifier, "approved fact id", "unapproved marker", True)
    unmarked = []
    for node in document.nodes:
        if not _body_visible(node):
            continue
        parent, approved = node, False
        while parent is not None:
            if parent.attrs.get("data-std-fact") in expected:
                approved = True
                break
            parent = parent.parent
        if not approved:
            unmarked.extend(normalize_text(child) for child in node.children
                            if isinstance(child, str) and normalize_text(child))
    add("facts.approved_text", "critical" if unmarked else "info", "fail" if unmarked else "pass",
        "body", "all visible source text belongs to approved facts", unmarked, bool(unmarked))
    _semantics(document, markers, expected, plan, add)
    _render_checks(plan, expected, render_evidence, report["planSha256"], report["artifactSha256"], add)
    return finish()
