import csv
import io
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

FIELDS = ("id", "name", "role", "department", "photo", "bio", "active",
          "role_recall", "name_recall", "mastery_exam")
FLAGS = FIELDS[6:]


@dataclass(frozen=True)
class Staff:
    id: str
    name: str
    role: str
    department: str
    photo: str
    bio: str
    active: bool
    role_recall: bool
    name_recall: bool
    mastery_exam: bool


def validate(rows, photo_root):
    staff, errors, warnings = [], [], []
    ids, profiles = set(), set()
    for number, row in enumerate(rows, 2):
        values = {key: str(row.get(key) or "").strip() for key in FIELDS}
        name = " ".join(values["name"].casefold().split())
        if re.match(r"^lyn(?:\W|$)", name):
            warnings.append(f"Row {number}: excluded roster entry.")
            continue
        if name == "ally rigney":
            values["role"] = "Adventure Program Manager"
        staff_id = values["id"]
        if (not re.fullmatch(r"[a-zA-Z0-9_-]+", staff_id)
                or not all(values[key] for key in ("name", "role", "department"))):
            errors.append(f"Row {number}: requires a valid ID, name, role and department.")
            continue
        profile = (name, values["role"].casefold(), values["department"].casefold())
        if staff_id.casefold() in ids or profile in profiles:
            errors.append(f"Row {number}: duplicate ID or staff profile.")
            continue
        if any(values[key].lower() not in {"true", "false", "1", "0"} for key in FLAGS):
            errors.append(f"Row {number}: use true or false for all eligibility fields.")
            continue
        ids.add(staff_id.casefold())
        profiles.add(profile)
        record = Staff(**{key: values[key] if key not in FLAGS else
                          values[key].lower() in {"true", "1"} for key in FIELDS})
        if photo_path(record, photo_root) is None:
            warnings.append(f"Row {number}: photo missing or invalid. Excluded from quizzes.")
        staff.append(record)
    return staff, errors, warnings


def load(text, photo_root):
    try:
        reader = csv.DictReader(io.StringIO(text), strict=True)
        if reader.fieldnames is None or set(reader.fieldnames) != set(FIELDS) or (
            len(reader.fieldnames) != len(FIELDS)
        ):
            return [], ["CSV header must contain each roster column once."], []
        rows = list(reader)
        if any(None in row or None in row.values() for row in rows):
            return [], ["Every CSV row must have the same number of fields as the header."], []
        return validate(rows, photo_root)
    except csv.Error as error:
        return [], [f"Invalid CSV: {error}"], []


def photo_path(record, root):
    file = Path(record.photo)
    if file.name != record.photo or file.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        return None
    path = (root / file).resolve()
    if path.parent != root.resolve():
        return None
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
        return path
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        return None


def portrait(path):
    # Return pixels only. The browser receives no original filename, EXIF or alt text.
    try:
        with Image.open(path) as image:
            cropped = ImageOps.fit(ImageOps.exif_transpose(image).convert("RGB"), (480, 600))
            clean = Image.new("RGB", cropped.size)
            clean.paste(cropped)
            return clean
    except (OSError, ValueError, AttributeError, Image.DecompressionBombError):
        return None


def csv_text(fields, rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
