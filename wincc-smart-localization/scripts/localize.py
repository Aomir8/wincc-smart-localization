import argparse
import base64
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import UUID

from hmi_format import (
    decode, language_values, plain_text, render_translation, replace_value,
    translation_parts, wincc_hash,
)


SCRIPTS = Path(__file__).resolve().parent
SLOTS = range(32)
HASH_FIELDS = [f"Hashcode{index}" for index in range(4)]


def unique_keys(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("JSON contains a duplicate key")
    return result


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique_keys)


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sql_string(value):
    return "NULL" if value is None else "N'" + value.replace("'", "''") + "'"


def sql_blob(value):
    return "NULL" if value is None else "0x" + value.hex()


def blob_bytes(value):
    return None if value is None else base64.b64decode(value, validate=True)


def b64(value):
    return None if value is None else base64.b64encode(value).decode("ascii")


def invoke_bridge(options, **arguments):
    shell = options.get("powershell") or shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not shell:
        raise ValueError("Run this tool on Windows with PowerShell and WinCC-compatible SQL Server LocalDB")
    command = [shell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
               "-File", str(SCRIPTS / "localdb.ps1")]
    if arguments["Action"] == "Query":
        arguments["LocalDbVersion"] = options.get("localdb_version")
        arguments["LocalDbExe"] = options.get("localdb_exe")
    for name, value in arguments.items():
        if value is not None:
            command.extend(("-" + name, str(value)))
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode:
        error = (result.stderr + result.stdout).decode("utf-8", errors="replace").strip()
        raise RuntimeError(error or f"PowerShell failed with exit code {result.returncode}")


def run_sql(options, project, folder, operation, sql):
    query = folder / (operation + ".sql")
    result = folder / (operation + ".json")
    query.write_text(sql, encoding="utf-8", newline="")
    invoke_bridge(options, Action="Query", Project=project, SqlFile=query, ResultFile=result)
    return load_json(result)


def snapshot(options, source, destination, culture=None):
    destination.mkdir()
    invoke_bridge(options, Action="Snapshot", Project=source, Destination=destination, Culture=culture)
    return destination / source.name


def inventory_sql(check=False):
    occupied = []
    for slot in SLOTS:
        field = f"[Language{slot}]"
        occupied.append(
            f"SELECT {slot} AS Slot WHERE EXISTS (SELECT 1 FROM dbo.HmiTextTable WHERE DATALENGTH({field})>0) "
            f"OR EXISTS (SELECT 1 FROM dbo.HmiFontListTable WHERE DATALENGTH({field})>0) "
            f"OR EXISTS (SELECT 1 FROM dbo.HmiImageDataTable WHERE {field} IS NOT NULL)"
        )
    query = (SCRIPTS / "read_project.sql").read_text(encoding="utf-8")
    query = query.replace("-- OCCUPIED_SLOTS", "\nUNION ALL\n".join(occupied) + ";")
    if check:
        query = "DBCC CHECKDB WITH NO_INFOMSGS, ALL_ERRORMSGS;\n" + query
    return query


def project_model(query_result):
    project, languages, runtime, settings, columns, device_fonts, occupied, font_lists, texts = query_result["results"]
    # The byte after the edition string is the length of the product version string.
    if len(project) != 1 or not (blob_bytes(project[0]["Metadata"]) or b"").startswith(b"\x0eEdition: SMART"):
        raise ValueError("This file is outside the supported WinCC flexible SMART project schema")
    if len(settings) != 1:
        raise ValueError("Expected one active project language settings object")
    if len({item["FolderId"] for item in languages}) != 1:
        raise ValueError("Expected one project language folder")
    active = [item for item in languages if not item["Deleted"] and not item["Destroyed"]]
    by_culture = {item["Culture"].casefold(): item for item in active}
    by_slot = {item["Slot"]: item for item in active}
    if not active or len(by_culture) != len(active) or len(by_slot) != len(active) or set(by_slot) - set(SLOTS):
        raise ValueError("Project language slots are invalid or ambiguous")
    text_columns = {row["ColumnName"]: row for row in columns if row["TableName"] == "HmiTextTable"}
    for slot in SLOTS:
        column = text_columns.get(f"Language{slot}", {})
        if column.get("TypeName") != "nvarchar" or column.get("MaxBytes", 0) == 0:
            raise ValueError(f"Unsupported SQL type for text slot {slot}")
    return {"project": project[0], "active": active, "by_culture": by_culture, "runtime": runtime,
            "settings": settings[0], "text_columns": text_columns, "device_fonts": device_fonts,
            "occupied": {item["Slot"] for item in occupied} | {item["Slot"] for item in languages},
            "fonts": font_lists, "texts": texts}


def select_languages(model, args):
    if not re.fullmatch(r"[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8}){1,3}", args.target):
        raise ValueError("Use a specific target locale such as fr-FR, ru-RU, or es-ES")
    segments = args.target.split("-")
    target = "-".join([segments[0].lower()] + [x.title() if len(x) == 4 else x.upper() for x in segments[1:]])
    target_record = model["by_culture"].get(target.casefold())
    if target_record:
        target, target_slot = target_record["Culture"], target_record["Slot"]
    else:
        unused = set(SLOTS) - model["occupied"]
        if not unused:
            raise ValueError("No unused project language slot is available")
        target_slot = min(unused)
    sources = {key: item for key, item in model["by_culture"].items() if key != target.casefold()}
    if args.source:
        source = sources.get(args.source.casefold())
    else:
        english = [item for key, item in sources.items() if key.startswith("en-")]
        if len(english) > 1:
            raise ValueError("Multiple English project languages found. Specify --source with the authoritative locale")
        source = english[0] if english else sources.get("zh-cn")
        if not source and len(sources) == 1:
            source = next(iter(sources.values()))
    if not source:
        available = ", ".join(item["Culture"] for item in sources.values())
        raise ValueError(f"Cannot identify the source language. Specify --source from: {available}")
    fallback = None
    if args.fallback and args.fallback.casefold() != "none":
        fallback = sources.get(args.fallback.casefold())
        if not fallback:
            raise ValueError("The requested fallback must be an active project language other than the target")
    elif not args.fallback and source["Culture"].casefold().startswith("en-"):
        fallback = sources.get("zh-cn")
    if fallback == source:
        fallback = None
    return {"target": target, "slot": target_slot, "source": source, "fallback": fallback,
            "new": target_record is None, "mode": args.mode, "overwrite": args.overwrite}


def row_content(row):
    blob = blob_bytes(row["TextHashtable"])
    return blob, language_values(*decode(blob))


def project_inventory(model, plan):
    entries, unsupported = [], []
    empty = 0
    for row in model["texts"]:
        id_text = row["Id"]
        context = [row[key] for key in ("GreatGrandparentName", "GrandparentName", "ParentName", "ObjectName") if row[key]]
        try:
            _, values = row_content(row)
            choices = [item for item in (plan["source"], plan["fallback"]) if item]
            source_text, source_culture = "", None
            for item in choices:
                culture = item["Culture"]
                raw = values.get(culture.casefold(), "")
                if plain_text(raw).strip():
                    source_text, source_culture = raw, culture
                    break
                if (row[f"Language{item['Slot']}"] or "").strip():
                    raise ValueError(f"{culture} is present in the SQL text index without matching project text")
            target_text = plain_text(values.get(plan["target"].casefold(), ""))
            parts = [part for part, protected in translation_parts(source_text) if not protected]
            if not source_text:
                empty += 1
                continue
            if plan["mode"] == "all" and target_text.strip() and not plan["overwrite"]:
                status = "keep_existing"
            else:
                status = "translate" if parts else "copy_literal"
            entries.append({"id": id_text, "kind": row["TextType"], "context": context,
                            "source_locale": source_culture, "source_text": plain_text(source_text),
                            "source_layout": source_text, "segments": parts,
                            "active_texts": {item["Culture"]: plain_text(values.get(item["Culture"].casefold(), ""))
                                             for item in model["active"]},
                            "target_text": target_text, "status": status})
        except ValueError as error:
            unsupported.append({"id": id_text, "context": context, "reason": str(error)})
    return {"languages": {row["Culture"]: row["Slot"] for row in model["active"]},
            "target": plan["target"], "target_slot": plan["slot"], "new_language": plan["new"],
            "mode": plan["mode"], "empty_sources": empty, "unsupported": unsupported, "entries": entries}


def scan(args):
    project = args.project.resolve(strict=True)
    if not project.is_file() or project.suffix.casefold() != ".hmismart":
        raise ValueError("Provide a saved .hmismart project file")
    work = args.work_dir.resolve()
    work.mkdir(parents=True)
    options = {key: getattr(args, key) for key in ("powershell", "localdb_exe", "localdb_version")}
    copy = snapshot(options, project, work / "snapshot", args.target)
    raw = run_sql(options, copy, work, "snapshot", inventory_sql())
    model = project_model(raw)
    plan = select_languages(model, args)
    report = project_inventory(model, plan)
    report["database_version"] = raw["database_version"]
    save_json(work / "inventory.json", report)
    save_json(work / "plan.json", {"project_file": project.name, "options": options, "plan": plan})
    print(f"Inventory: {work / 'inventory.json'}")
    print(f"Project texts with a source: {len(report['entries'])}; unsupported: {len(report['unsupported'])}")


def select_translations(inventory, translations):
    if not isinstance(translations, dict):
        raise ValueError("Translations must be a JSON object mapping each record ID to its translated segments")
    selected = {entry["id"]: entry for entry in inventory["entries"]}
    unknown = set(translations) - selected.keys()
    if unknown:
        raise ValueError(f"Translation IDs are not in this inventory: {', '.join(sorted(unknown)[:8])}")
    if inventory["mode"] == "all":
        required = {id_text for id_text, row in selected.items() if row["status"] == "translate"}
        missing = required - translations.keys()
        extra = translations.keys() - required
        if missing or extra:
            example = ", ".join(sorted(missing | extra)[:8])
            raise ValueError(f"Bulk scope mismatch: {len(missing)} missing, {len(extra)} unexpected. IDs: {example}")
        literals = {id_text for id_text, row in selected.items() if row["status"] == "copy_literal"}
        translations = {**translations, **{id_text: [] for id_text in literals}}
    if not translations and not inventory["new_language"]:
        raise ValueError("There are no requested text changes to apply")
    if not translations and inventory["mode"] == "selected":
        raise ValueError("Choose at least one record ID in selected mode")
    return {id_text: render_translation(selected[id_text]["source_layout"], value)
            for id_text, value in translations.items()}


def language_patch(model, plan):
    target = plan["target"].casefold()
    templates = {}
    for folder in {item["FolderId"] for item in model["device_fonts"]}:
        rows = [item for item in model["device_fonts"] if item["FolderId"] == folder and item["Id"]]
        if not rows or any(item["Culture"].casefold() == target for item in rows):
            raise ValueError("A device has missing font templates or a duplicate target font configuration")
        templates[folder] = rows[0]["Id"]
    if not templates:
        raise ValueError("No supported device language and font folder found")
    reference = model["settings"]["ReferenceCulture"] or ""
    ordered = [model["by_culture"].get(reference.casefold()), plan["source"], *model["active"]]
    fallback_slots = list(dict.fromkeys(item["Slot"] for item in ordered if item))
    patch = (SCRIPTS / "add_project_language.sql").read_text(encoding="utf-8")
    replacements = {"@TARGET_CULTURE@": sql_string(plan["target"]), "@TARGET_SLOT@": str(plan["slot"]),
                    "@PROJECT_LANGUAGE_TEMPLATE@": sql_string(str(UUID(model["active"][0]["Id"]))),
                    "@SLOT_COLUMN@": f"[Language{plan['slot']}]",
                    "@FONT_FALLBACK_COLUMNS@": ",".join(f"f.[Language{slot}]" for slot in fallback_slots),
                    "-- FONT_TEMPLATES": "INSERT #FontTemplates (Id) VALUES " + ",".join(
                        f"({sql_string(str(UUID(value)))})" for value in templates.values()) + ";"}
    for key, value in replacements.items():
        patch = patch.replace(key, value)
    return patch, set(templates), fallback_slots


def write_texts(model, plan, translated):
    slot_field = f"Language{plan['slot']}"
    target = plan["target"].casefold()
    languages = {row["Slot"]: row["Culture"] for row in model["active"]}
    languages[plan["slot"]] = plan["target"]
    cultures = [languages[slot] for slot in sorted(languages)]
    max_bytes = model["text_columns"][slot_field]["MaxBytes"]
    expected, rows = {}, []
    dormant = 0
    for record in model["texts"]:
        id_text = record["Id"]
        if not plan["new"] and id_text not in translated:
            continue
        old_blob, values = row_content(record)
        new_blob, cache = old_blob, record[slot_field]
        if id_text in translated:
            values[target] = translated[id_text]
            new_blob = replace_value(old_blob, plan["target"], values[target])
            cache = plain_text(values[target])
        elif plan["new"] and plain_text(values.get(target, "")).strip():
            cache = plain_text(values[target])
            dormant += 1
        units = len(cache.encode("utf-16-le")) // 2 if cache is not None else 0
        if max_bytes > 0 and units > max_bytes // 2:
            raise ValueError(f"Text {id_text} exceeds the target SQL text field limit of {max_bytes // 2} UTF-16 units")
        if id_text in translated and not record["IsFormattedText"] and 0 < (record["MaxLength"] or 0) < units:
            raise ValueError(f"Text {id_text} exceeds the WinCC text object limit of {record['MaxLength']} UTF-16 units")
        hashes = wincc_hash(cultures, values)
        if (new_blob, cache, hashes) == (old_blob, record[slot_field], tuple(record[key] for key in HASH_FIELDS)):
            continue
        values_sql = (sql_string(str(UUID(id_text))), sql_blob(old_blob), sql_string(record[slot_field]),
                      sql_blob(new_blob), sql_string(cache), *map(str, hashes))
        rows.append("(" + ",".join(values_sql) + ")")
        expected[id_text] = {"TextHashtable": b64(new_blob), slot_field: cache, **dict(zip(HASH_FIELDS, hashes))}
    query = ["CREATE TABLE #Writes (Id uniqueidentifier PRIMARY KEY, OldBlob varbinary(max), OldCache nvarchar(max), "
             "NewBlob varbinary(max), NewCache nvarchar(max), H0 int, H1 int, H2 int, H3 int);"]
    for start in range(0, len(rows), 250):
        query.append("INSERT #Writes VALUES\n" + ",\n".join(rows[start:start + 250]) + ";")
    query.append(f"""
UPDATE t SET [{slot_field}]=w.NewCache, TextHashtable=w.NewBlob,
             Hashcode0=w.H0, Hashcode1=w.H1, Hashcode2=w.H2, Hashcode3=w.H3
FROM dbo.HmiTextTable t JOIN #Writes w ON w.Id=t.Id
WHERE (CONVERT(varbinary(max),t.TextHashtable)=w.OldBlob OR t.TextHashtable IS NULL AND w.OldBlob IS NULL)
  AND (CONVERT(varbinary(max),t.[{slot_field}])=CONVERT(varbinary(max),w.OldCache)
       OR t.[{slot_field}] IS NULL AND w.OldCache IS NULL);
IF @@ROWCOUNT<>(SELECT COUNT(*) FROM #Writes) THROW 50002, 'A source record changed. Scan the project again.', 1;
""")
    return "\n".join(query), expected, dormant


def verify(before, after, plan, expected, font_folders, font_fallback):
    expected_languages = {row["Culture"]: row["Slot"] for row in before["active"]}
    expected_languages[plan["target"]] = plan["slot"]
    if {row["Culture"]: row["Slot"] for row in after["active"]} != expected_languages:
        raise ValueError("Project languages differ from the expected mapping after reattaching")
    for key in ("project", "runtime", "settings"):
        if before[key] != after[key]:
            raise ValueError(f"Unexpected change to project {key}")
    prior_fonts = {item["Id"]: item for item in before["device_fonts"] if item["Id"]}
    current_fonts = {item["Id"]: item for item in after["device_fonts"] if item["Id"]}
    added = [item for key, item in current_fonts.items() if key not in prior_fonts]
    if (any(current_fonts.get(key) != item for key, item in prior_fonts.items())
            or {item["FolderId"] for item in added} != font_folders or len(added) != len(font_folders)
            or any(item["Culture"] != plan["target"] for item in added)):
        raise ValueError("Unexpected device language font settings after reattaching")
    after_fonts = {row["Id"]: row for row in after["fonts"]}
    for row in before["fonts"]:
        updated = dict(row)
        if plan["new"] and row["Active"] and row[f"Language{plan['slot']}"] is None:
            updated[f"Language{plan['slot']}"] = next((row[f"Language{i}"] for i in font_fallback
                                                       if row[f"Language{i}"] is not None), None)
        if after_fonts.pop(row["Id"], None) != updated:
            raise ValueError(f"Unexpected font list change for {row['Id']}")
    if after_fonts:
        raise ValueError("Unexpected font list records were added")
    after_texts = {row["Id"]: row for row in after["texts"]}
    for row in before["texts"]:
        updated = {**row, **expected.get(row["Id"], {})}
        if after_texts.pop(row["Id"], None) != updated:
            raise ValueError(f"Unexpected project text change for {row['Id']}")
    if after_texts:
        raise ValueError("Unexpected project text records were added")
    return expected_languages


def apply(args):
    work = args.work_dir.resolve(strict=True)
    output = args.output_dir.resolve()
    if output.exists():
        raise ValueError("Use a new output directory so an existing project cannot be overwritten")
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = load_json(work / "plan.json")
    filename = manifest["project_file"]
    if Path(filename).name != filename or Path(filename).suffix.casefold() != ".hmismart":
        raise ValueError("Invalid snapshot project filename")
    options, plan = manifest["options"], manifest["plan"]
    raw = load_json(work / "snapshot.json")
    model = project_model(raw)
    inventory = project_inventory(model, plan)
    if inventory["unsupported"] and (plan["new"] or plan["mode"] == "all"):
        raise ValueError("Unsupported project text records are listed in inventory.json. No project was changed")
    translated = select_translations(inventory, load_json(args.translations))
    if args.expect_count is not None and len(translated) != args.expect_count:
        raise ValueError(f"Expected {args.expect_count} text records, got {len(translated)}")
    language_sql, font_folders, font_fallback = language_patch(model, plan) if plan["new"] else ("", set(), [])
    texts_sql, expected, dormant = write_texts(model, plan, translated)
    sql = "SET NOCOUNT ON; SET XACT_ABORT ON; BEGIN TRANSACTION;\n" + language_sql + texts_sql + "\nCOMMIT TRANSACTION;"
    with tempfile.TemporaryDirectory(prefix=".wincc-localize-", dir=output.parent) as staging:
        stage = Path(staging).resolve()
        if stage.parent != output.parent:
            raise ValueError("Temporary project path escaped the output directory")
        copy = snapshot(options, work / "snapshot" / filename, stage / "project")
        applied = run_sql(options, copy, stage, "apply", sql)
        checked = run_sql(options, copy, stage, "verify", inventory_sql(check=True))
        if applied["database_version"] != raw["database_version"] or checked["database_version"] != raw["database_version"]:
            raise ValueError("The project database format changed unexpectedly")
        languages = verify(model, project_model(checked), plan, expected, font_folders, font_fallback)
        save_json(copy.parent / "localization-report.json", {
            "project": filename, "database_format": raw["database_version"], "languages": languages,
            "target": plan["target"], "added_project_language": plan["new"], "mode": plan["mode"],
            "translated_or_copied": len(translated), "changed_text_rows_including_hash_refresh": len(expected),
            "restored_existing_target_cache_rows": dormant, "empty_sources": inventory["empty_sources"],
            "preserved_existing": sum(row["status"] == "keep_existing" for row in inventory["entries"]),
            "source_usage": {locale: sum(row["id"] in translated and row["source_locale"] == locale
                                         for row in inventory["entries"]) for locale in
                             sorted({row["source_locale"] for row in inventory["entries"]})},
            "rows": [{"id": id_text, "target": plain_text(value)} for id_text, value in translated.items()],
            "database_check": "passed", "wincc_ui_check": "not performed",
        })
        copy.parent.rename(output)
    print(f"Localized project: {output / filename}")
    print(f"Target: {plan['target']}; text records: {len(translated)}; database readback and integrity check passed.")


def main():
    parser = argparse.ArgumentParser(description="Localize a copy of a WinCC flexible SMART project offline")
    commands = parser.add_subparsers(dest="operation", required=True)
    inspect = commands.add_parser("scan", help="Snapshot a project and export its project-language text inventory")
    inspect.add_argument("--project", type=Path, required=True)
    inspect.add_argument("--work-dir", type=Path, required=True)
    inspect.add_argument("--target", required=True)
    inspect.add_argument("--source")
    inspect.add_argument("--fallback", help="Fallback source locale, or 'none'")
    inspect.add_argument("--mode", choices=("all", "selected"), default="all")
    inspect.add_argument("--overwrite", action="store_true", help="Replace existing target text in bulk mode")
    inspect.add_argument("--powershell", help="Installed PowerShell executable path, if not found on PATH")
    inspect.add_argument("--localdb-exe", help="Installed SqlLocalDB.exe path, if not found automatically")
    inspect.add_argument("--localdb-version", help="Installed LocalDB engine version matching the WinCC project")
    write = commands.add_parser("apply", help="Write a verified localized project into a new directory")
    write.add_argument("--work-dir", type=Path, required=True)
    write.add_argument("--translations", type=Path, required=True)
    write.add_argument("--output-dir", type=Path, required=True)
    write.add_argument("--expect-count", type=int)
    args = parser.parse_args()
    try:
        (scan if args.operation == "scan" else apply)(args)
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if not sys.stdout.isatty():
        sys.stdout.reconfigure(encoding="utf-8")
    if not sys.stderr.isatty():
        sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
