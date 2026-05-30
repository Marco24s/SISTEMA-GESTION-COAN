import re
import unicodedata
import zipfile
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree

from django.db import transaction
from django.utils import timezone

from core.models import Unit

from .models import ProcurementDestination, TenderProcess


SHEET_NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkg_rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def import_tender_processes_from_xlsx(uploaded_file, year, user):
    workbook = _read_xlsx(uploaded_file)
    stats = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "destinations": set(),
        "warnings": [],
    }

    with transaction.atomic():
        for sheet_name, rows in workbook.items():
            destination_code = sheet_name.strip().upper()
            if destination_code == "RESUMEN":
                continue

            destination, _ = ProcurementDestination.objects.get_or_create(
                code=destination_code,
                defaults={"name": destination_code},
            )
            unit = Unit.objects.filter(name__iexact=destination_code).first()
            stats["destinations"].add(destination_code)

            for row_number, row in rows.items():
                if row_number < 3:
                    continue

                process_number = _clean_text(row.get("A"))
                process_name = _clean_text(row.get("C"))
                if not process_number:
                    if process_name:
                        stats["skipped"] += 1
                    continue

                defaults = {
                    "unit": unit,
                    "destination": destination,
                    "expediente": _clean_text(row.get("B")),
                    "name": process_name or process_number,
                    "process_type": _map_process_type(row.get("D")),
                    "opening_date": _parse_opening_date(row.get("E")),
                    "status": _map_status(row.get("F")),
                    "amount_ars": _to_decimal(row.get("G")),
                    "has_oca": _to_bool(row.get("I")),
                    "currency": _detect_currency(row.get("L")),
                    "foreign_amount": _to_decimal(row.get("K")),
                    "exchange_rate": _extract_exchange_rate(row.get("L")),
                    "exchange_rate_date": _extract_exchange_rate_date(row.get("L")),
                    "source": "COMPRAR.GOB.AR",
                    "notes": _build_notes(row),
                    "is_active": True,
                }
                if user and getattr(user, "is_authenticated", False):
                    defaults["created_by"] = user

                _, created = TenderProcess.objects.update_or_create(
                    year=year,
                    process_number=process_number,
                    defaults=defaults,
                )
                if created:
                    stats["created"] += 1
                else:
                    stats["updated"] += 1

    stats["destinations"] = sorted(stats["destinations"])
    return stats


def _read_xlsx(uploaded_file):
    uploaded_file.seek(0)
    with zipfile.ZipFile(uploaded_file) as archive:
        shared_strings = _read_shared_strings(archive)
        workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        rels_root = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels_root.findall("pkg_rel:Relationship", SHEET_NS)
        }

        sheets = {}
        for sheet in workbook_root.findall("main:sheets/main:sheet", SHEET_NS):
            name = sheet.attrib["name"]
            rel_id = sheet.attrib["{%s}id" % SHEET_NS["rel"]]
            target = rel_targets[rel_id].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            sheets[name] = _read_sheet(archive, target, shared_strings)
        return sheets


def _read_shared_strings(archive):
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []

    values = []
    for item in root.findall("main:si", SHEET_NS):
        parts = []
        for text_node in item.findall(".//main:t", SHEET_NS):
            parts.append(text_node.text or "")
        values.append("".join(parts))
    return values


def _read_sheet(archive, path, shared_strings):
    root = ElementTree.fromstring(archive.read(path))
    rows = {}
    for row_node in root.findall(".//main:sheetData/main:row", SHEET_NS):
        row_index = int(row_node.attrib["r"])
        values = {}
        for cell in row_node.findall("main:c", SHEET_NS):
            ref = cell.attrib.get("r", "")
            column = re.sub(r"\d+", "", ref)
            values[column] = _cell_value(cell, shared_strings)
        rows[row_index] = values
    return rows


def _cell_value(cell, shared_strings):
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        text_node = cell.find(".//main:t", SHEET_NS)
        return text_node.text if text_node is not None else None

    value_node = cell.find("main:v", SHEET_NS)
    if value_node is None:
        return None

    value = value_node.text
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (ValueError, IndexError):
            return value
    if cell_type == "b":
        return value == "1"
    return value


def _clean_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize(value):
    text = _clean_text(value) or ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def _map_process_type(value):
    text = _normalize(value)
    if "public" in text:
        return "PUBLICA"
    if "privad" in text:
        return "PRIVADA"
    if "direct" in text:
        return "CONTRATACION_DIRECTA"
    return "OTRO"


def _map_status(value):
    text = _normalize(value)
    if "preadjudic" in text:
        return "PREADJUDICADO"
    if "disponible" in text:
        return "DISPONIBLE_ADJUDICAR"
    if "adjudic" in text:
        return "ADJUDICADO"
    if "evaluacion" in text:
        return "EN_EVALUACION"
    if "apertura" in text:
        return "EN_APERTURA"
    if "fracas" in text:
        return "FRACASADO"
    if "desierto" in text:
        return "DESIERTO"
    if "sin efecto" in text:
        return "DEJADO_SIN_EFECTO"
    return "PUBLICADO"


def _to_decimal(value):
    if value in (None, ""):
        return None
    text = str(value).strip().replace("$", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _to_bool(value):
    text = _normalize(value)
    if text in ["si", "s", "true", "1"]:
        return True
    if text in ["no", "n", "false", "0"]:
        return False
    return None


def _detect_currency(note):
    text = _normalize(note)
    if "usd" in text or "dolar" in text:
        return "USD"
    if "eur" in text or "euro" in text:
        return "EUR"
    return "ARS"


def _extract_exchange_rate(note):
    text = _clean_text(note)
    if not text:
        return None
    match = re.search(r"\$?\s*(\d+(?:[.,]\d+)?)", text)
    return _to_decimal(match.group(1)) if match else None


def _extract_exchange_rate_date(note):
    text = _clean_text(note)
    if not text:
        return None
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
    if not match:
        return None
    day, month, year = [int(part) for part in match.groups()]
    if year < 100:
        year += 2000
    try:
        return datetime(year, month, day).date()
    except ValueError:
        return None


def _parse_opening_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        parsed = datetime(1899, 12, 30) + timedelta(days=float(value))
        return timezone.make_aware(parsed)

    text = str(value).strip().replace("Hrs.", "").replace("Hrs", "").replace("hs.", "").strip()
    for fmt in ["%d/%m/%Y %H:%M", "%d/%m/%y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"]:
        try:
            parsed = datetime.strptime(text, fmt)
            return timezone.make_aware(parsed)
        except ValueError:
            continue
    return None


def _build_notes(row):
    parts = []
    raw_status = _clean_text(row.get("F"))
    sum_flag = _clean_text(row.get("H"))
    published_flag = _clean_text(row.get("J"))
    exchange_note = _clean_text(row.get("L"))

    if raw_status:
        parts.append(f"Estado original Excel: {raw_status}")
    if sum_flag:
        parts.append(f"Marca Suma si: {sum_flag}")
    if published_flag:
        parts.append(f"Marca publicado: {published_flag}")
    if exchange_note:
        parts.append(f"Nota moneda: {exchange_note}")
    return "\n".join(parts) if parts else None
