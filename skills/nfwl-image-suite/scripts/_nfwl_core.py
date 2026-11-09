"""Portable deterministic helpers for the three nfwl skill suites (Python 3.10+).

The Agent writes creative content; this module validates, scores, renders and
records it. It never calls an LLM, reads credentials, or writes a SKU database.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import html
import json
import math
import re
import shutil
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"
DIMENSIONS = ["pain_point", "function", "material", "operation", "accessory", "extra"]
IMAGE_TYPES = {
    "main": (1600, 1600), "size": (1600, 1600),
    "detail": (1600, 1600), "feature": (1600, 1600),
    "comparison": (1600, 1600), "lifestyle": (1600, 1600),
    "a_plus_hero": (970, 600), "a_plus_size": (970, 600),
    "a_plus_detail": (970, 600), "a_plus_steps": (970, 600),
    "a_plus_comparison": (970, 600), "a_plus_scene": (970, 600),
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path, value):
    """Exclusive writes: callers select a new task/revision, never overwrite."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    with p.open("x", encoding="utf-8", newline="\n") as f:
        f.write(content + ("" if content.endswith("\n") else "\n"))
    return str(p.resolve())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def issue(code, path, message, severity="error"):
    return {"code": code, "path": path, "message": message, "severity": severity}


def schema_errors(value, schema, root=None, path="$"):
    """Validate the documented JSON-Schema subset used by this package.

    Schemas also validate with Draft202012Validator. Supported: local $ref,
    type, required, properties, additionalProperties, enum, const, items,
    min/maxItems, min/maxLength, minimum/maximum, uniqueItems, anyOf.
    """
    root = root or schema
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/"):
            return [issue("schema_reference", path, "Only in-document references are supported")]
        target = root
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        return schema_errors(value, target, root, path)
    errors = []
    if "anyOf" in schema and not any(not schema_errors(value, s, root, path) for s in schema["anyOf"]):
        errors.append(issue("schema_anyOf", path, "Value does not match an allowed shape"))
    kinds = {
        "object": lambda v: isinstance(v, dict), "array": lambda v: isinstance(v, list),
        "string": lambda v: isinstance(v, str), "boolean": lambda v: isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool), "null": lambda v: v is None,
    }
    types = schema.get("type", [])
    types = [types] if isinstance(types, str) else types
    if types and not any(kinds[t](value) for t in types):
        return errors + [issue("schema_type", path, "Expected " + "/".join(types))]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(issue("schema_enum", path, "Value outside allowed choices"))
    if "const" in schema and value != schema["const"]:
        errors.append(issue("schema_const", path, "Unexpected constant"))
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(issue("schema_required", f"{path}/{key}", "Required field missing"))
        props = schema.get("properties", {})
        for key, item in value.items():
            if key in props:
                errors.extend(schema_errors(item, props[key], root, f"{path}/{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(issue("schema_extra", f"{path}/{key}", "Unexpected field"))
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(schema_errors(item, schema["additionalProperties"], root, f"{path}/{key}"))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", float("inf")):
            errors.append(issue("schema_length", path, "Array length outside limits"))
        if schema.get("uniqueItems") and len({digest(x) for x in value}) != len(value):
            errors.append(issue("schema_unique", path, "Duplicate items"))
        for i, item in enumerate(value):
            errors.extend(schema_errors(item, schema.get("items", {}), root, f"{path}/{i}"))
    if isinstance(value, str) and (len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", float("inf"))):
        errors.append(issue("schema_length", path, "Text length outside limits"))
    if isinstance(value, (float, int)) and not isinstance(value, bool):
        if value < schema.get("minimum", -float("inf")) or value > schema.get("maximum", float("inf")):
            errors.append(issue("schema_range", path, "Number outside limits"))
    return errors


def fact_index(request):
    return {f["id"]: f for f in request.get("product", {}).get("facts", [])}


def confirmed_facts(request):
    source_ids = {s["id"] for s in request.get("product", {}).get("sources", [])}
    return {k: v for k, v in fact_index(request).items()
            if v.get("status") == "confirmed" and v.get("source_ids")
            and set(v["source_ids"]).issubset(source_ids)}


def check_product(request):
    errors = []
    product = request.get("product", {})
    ids = [f.get("id") for f in product.get("facts", [])]
    if len(set(ids)) != len(ids):
        errors.append(issue("duplicate_fact", "$/product/facts", "Fact ids must be unique"))
    sources = [s.get("id") for s in product.get("sources", [])]
    if len(set(sources)) != len(sources):
        errors.append(issue("duplicate_source", "$/product/sources", "Source ids must be unique"))
    for i, fact in enumerate(product.get("facts", [])):
        if fact.get("status") == "confirmed" and fact["id"] not in confirmed_facts(request):
            errors.append(issue("missing_source", f"$/product/facts/{i}", "Confirmed facts require existing source ids"))
    return errors


def prepare(request):
    facts = confirmed_facts(request)
    return {
        "schema_version": "1.0", "input_sha256": digest(request),
        "sku_id": request.get("product", {}).get("sku_id"),
        "usable_facts": list(facts.values()),
        "unresolved_facts": [f for f in fact_index(request).values() if f["id"] not in facts],
        "restrictions": request.get("product", {}).get("restrictions", []),
        "issues": check_product(request),
        "note": "Only usable_facts can support product claims. Human approval is recorded outside this skill.",
    }


def norm(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text)).casefold()).strip()


def words(text):
    return re.findall(r"[^\W_]+", norm(text), flags=re.UNICODE)


UNIT_ALIASES = {
    "w": "w", "watts": "w", "watt": "w", "瓦": "w",
    "v": "v", "volts": "v", "volt": "v", "伏": "v",
    "ml": "ml", "milliliters": "ml", "毫升": "ml",
    "l": "l", "liters": "l", "litres": "l", "升": "l",
    "qt": "qt", "quarts": "qt", "quart": "qt",
    "cm": "cm", "厘米": "cm", "mm": "mm", "毫米": "mm", "in": "in", "inch": "in", "inches": "in",
    "g": "g", "克": "g", "kg": "kg", "千克": "kg", "lb": "lb", "lbs": "lb",
    "°c": "c", "℃": "c", "celsius": "c", "°f": "f", "fahrenheit": "f",
    "pcs": "count", "pieces": "count", "piece": "count", "件": "count", "个": "count",
    "minutes": "min", "minute": "min", "min": "min", "分钟": "min", "years": "year", "year": "year", "年": "year",
}
_unit_pattern = "|".join(re.escape(u) for u in sorted(UNIT_ALIASES, key=len, reverse=True))
QUANTITY = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)(?:\s*(" + _unit_pattern + r"))(?![a-z])", re.I)
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w.])")


def quantities(text):
    return [(float(m[1].replace(",", ".")), UNIT_ALIASES[m[2].casefold()]) for m in QUANTITY.finditer(norm(text))]


def fact_text(fact):
    value = fact.get("value", "")
    if isinstance(value, list):
        return " ".join(f"{x} {fact.get('unit', '')}" for x in value)
    return f"{value} {fact.get('unit', '')} " + " ".join(fact.get("allowed_claims", []))


def rules_for(skill_dir):
    return read_json(Path(skill_dir) / "references" / "customer-rules.json")


def check_claim(text, refs, request, rules, path):
    errors = []
    facts = confirmed_facts(request)
    for ref in refs:
        if ref not in facts:
            errors.append(issue("unconfirmed_fact", path, f"Unknown/unconfirmed fact: {ref}"))
    if not refs:
        errors.append(issue("missing_evidence", path, "Declare the confirmed facts used by this field"))
    evidence_text = " ".join(fact_text(facts[x]) for x in refs if x in facts)
    for term in rules["forbidden_terms"]:
        pattern = r"(?<!\w)" + re.escape(norm(term)) + r"(?!\w)" if term.isascii() else re.escape(term)
        if re.search(pattern, norm(text)):
            errors.append(issue("forbidden_term", path, f"Customer prohibited expression: {term}"))
    for term in request.get("product", {}).get("competitor_brands", []):
        if norm(term) and norm(term) in norm(text):
            errors.append(issue("competitor_brand", path, f"Competitor brand: {term}"))
    for rule in request.get("product", {}).get("restrictions", []):
        for pattern in rule.get("patterns", []):
            if re.search(pattern, text, re.I):
                errors.append(issue("product_restriction", path, rule["message"]))
    for pattern, label in rules["claim_patterns"].items():
        hits = {norm(m.group()) for m in re.finditer(pattern, text, re.I)}
        evidence_hits = {norm(m.group()) for m in re.finditer(pattern, evidence_text, re.I)}
        exact_code = label in {"304 steel grade", "certification", "ingress rating"}
        if hits and (not evidence_hits or (exact_code and not hits.issubset(evidence_hits))):
            errors.append(issue("unsupported_claim", path, f"Evidence does not support {label}: {', '.join(sorted(hits))}"))
    allowed_q = quantities(evidence_text)
    for number, unit in quantities(text):
        if not any(unit == u and abs(number - n) < 1e-6 for n, u in allowed_q):
            errors.append(issue("unsupported_quantity", path, f"Unsupported quantity: {number:g} {unit}"))
    identity = str(request.get("product", {}).get("name", "")) + " " + str(request.get("product", {}).get("sku_id", ""))
    clean_text = text.replace(request.get("product", {}).get("sku_id", "\0"), "")
    allowed_numbers = {float(x.replace(",", ".")) for x in NUMBER.findall(norm(evidence_text + " " + identity))}
    for token in NUMBER.findall(norm(clean_text)):
        if float(token.replace(",", ".")) not in allowed_numbers:
            errors.append(issue("unsupported_number", path, f"No declared fact supports number {token}"))
    if re.search(r"https?://|www\.|[\w.+-]+@[\w.-]+\.[a-z]{2,}", text, re.I):
        errors.append(issue("external_link", path, "Links/contact information are prohibited in listing/selling copy"))
    if any(unicodedata.category(c) in {"So", "Cs"} and c not in {"°", "℃", "℉"} for c in text):
        errors.append(issue("decorative_symbol", path, "Emoji/decorative symbols are prohibited"))
    return errors


def binding_errors(request, result):
    errors = []
    if result.get("sku_id") != request.get("product", {}).get("sku_id"):
        errors.append(issue("sku_mismatch", "$/sku_id", "Result belongs to another SKU"))
    if result.get("input_sha256") != digest(request):
        errors.append(issue("input_version_mismatch", "$/input_sha256", "Result does not match this input snapshot"))
    return errors


def selling_review(request, result, rules):
    errors = check_product(request) + binding_errors(request, result)
    points = result.get("selling_points", [])
    seen_ids, seen_themes = set(), set()
    for i, point in enumerate(points):
        path = f"$/selling_points/{i}"
        if point["id"] in seen_ids:
            errors.append(issue("duplicate_point_id", path, "Selling point id repeated"))
        seen_ids.add(point["id"])
        if norm(point["theme"]) in seen_themes:
            errors.append(issue("duplicate_theme", path, "Each selling point needs a separate theme"))
        seen_themes.add(norm(point["theme"]))
        if point.get("status") == "confirmed":
            errors.append(issue("unauthorized_approval", path, "Generated selling points must remain drafts"))
        for field in ["text", "feature", "benefit"]:
            errors.extend(check_claim(point[field], point["fact_ids"], request, rules, path + "/" + field))
    if len(points) < 5:
        errors.append(issue("limited_points", "$/selling_points", "Fewer than five supported themes; do not invent more", "warning"))
    return qa_result(errors)


def qa_result(errors):
    return {"gate": "revise" if any(e["severity"] == "error" for e in errors) else "pass",
            "issues": errors, "semantic_review": "required",
            "human_approval": "pending",
            "limits": "Mechanical checks do not prove truth, single-theme quality, native language or visual fidelity."}


def request_combinations(request):
    return {(t["marketplace"], t["language"], s["id"])
            for t in request.get("targets", []) for s in request.get("strategies", [])}


def listing_review(request, result, rules):
    errors = check_product(request) + binding_errors(request, result)
    seen, seen_ids = set(), set()
    expected = request_combinations(request)
    for i, variant in enumerate(result.get("listing_variants", [])):
        root = f"$/listing_variants/{i}"
        if variant["id"] in seen_ids:
            errors.append(issue("duplicate_variant_id", root + "/id", "Variant ids must be unique for frontend selection"))
        seen_ids.add(variant["id"])
        key = (variant["marketplace"], variant["language"], variant["strategy_id"])
        if key in seen:
            errors.append(issue("duplicate_variant", root, "Duplicate market/language/strategy"))
        seen.add(key)
        if key not in expected:
            errors.append(issue("unexpected_variant", root, "Variant not requested"))
        title = variant["title"]
        if len(title) > rules["title_max_chars"]:
            errors.append(issue("title_length", root + "/title", f"Title has {len(title)} characters, maximum 75"))
        if any(c in title for c in rules["title_forbidden_chars"]):
            errors.append(issue("title_symbol", root + "/title", "Prohibited title punctuation"))
        if variant["language"] in rules["stop_words"]:
            repeated = [w for w, count in Counter(words(title)).items()
                        if count > 2 and w not in rules["stop_words"][variant["language"]]]
            if repeated:
                errors.append(issue("title_repeat", root + "/title", "Repeated substantive words: " + ", ".join(repeated)))
        if len(variant["bullets"]) != 5:
            errors.append(issue("bullet_count", root + "/bullets", "Exactly five bullets required"))
        all_fields = {"title": title, "description": variant["description"]}
        all_fields.update({f"bullets/{n}": b["text"] for n, b in enumerate(variant["bullets"])})
        for field, text in all_fields.items():
            errors.extend(check_claim(text, variant["evidence_map"].get(field, []), request, rules, root + "/" + field))
        approved_points = {p["id"] for p in request.get("selling_points", []) if p.get("status") == "confirmed"}
        themes = []
        for n, bullet in enumerate(variant["bullets"]):
            themes.append(norm(bullet["theme"]))
            if not bullet["selling_point_ids"] or not set(bullet["selling_point_ids"]).issubset(approved_points):
                errors.append(issue("unapproved_selling_point", f"{root}/bullets/{n}", "Bullets must use confirmed selling points"))
            if norm(bullet["text"]) in norm(variant["description"]):
                errors.append(issue("description_copy", root + "/description", "Description copies a complete bullet"))
        if len(set(themes)) != len(themes):
            errors.append(issue("bullet_theme_repeat", root + "/bullets", "Bullet themes overlap"))
        limit = request.get("field_limits", {}).get(variant["marketplace"], {}).get("search_terms_bytes")
        if limit is not None and len(variant.get("search_terms", "").encode("utf-8")) > limit:
            errors.append(issue("search_terms_bytes", root + "/search_terms", f"Search terms exceed configured {limit} UTF-8 bytes"))
    for key in expected - seen:
        errors.append(issue("missing_variant", "$/listing_variants", "Missing combination: " + "/".join(key)))
    pack = request.get("research", {})
    actual_targets = {(k.get("marketplace"), k.get("language")) for k in pack.get("keywords", []) if k.get("relevance",0) >= .5}
    market_ready = research_valid(pack) and all((t["marketplace"], t["language"]) in actual_targets for t in request.get("targets", []))
    if not market_ready:
        errors.append(issue("market_unverified", "$/research", "Market/keyword validation incomplete; copy is a draft", "warning"))
    result_qa = qa_result(errors)
    result_qa["market_validated"] = market_ready
    return result_qa


def research_valid(pack):
    source_ids = {s["id"] for s in pack.get("sources", [])}
    return (pack.get("mode") in {"live", "export"} and not pack.get("synthetic", False)
            and bool(pack.get("sources")) and bool(pack.get("keywords"))
            and all(k.get("source_ids") and set(k["source_ids"]).issubset(source_ids) for k in pack.get("keywords", [])))


def keyword_strategy(request):
    pack = request.get("research", {})
    rows = copy.deepcopy(pack.get("keywords", []))
    usable, excluded = [], []
    source_ids = {s["id"] for s in pack.get("sources", [])}
    for row in rows:
        if row.get("relevance", 0) < .5 or not row.get("source_ids") or not set(row["source_ids"]).issubset(source_ids):
            row["excluded_reason"] = "Low/unreviewed relevance or missing source"
            excluded.append(row)
        else:
            usable.append(row)
    groups = {}
    for row in usable:
        groups.setdefault((row["marketplace"], row["language"]), []).append(row)
    weights = request.get("keyword_weights", {"volume": .35, "relevance": .30, "purchase_rate": .15, "spr": .10, "cpc": .10})
    for group in groups.values():
        for row in group:
            parts, missing = {}, []
            for name, weight in weights.items():
                value = row.get(name)
                if value is None:
                    missing.append(name)
                    continue
                vals = [float(x[name]) for x in group if x.get(name) is not None]
                lo, hi = min(vals), max(vals)
                score = .5 if hi == lo else (float(value) - lo) / (hi - lo)
                if name == "relevance":
                    score = float(value)
                if name in {"spr", "cpc"}:
                    score = 1 - score
                parts[name] = (score, weight)
            total = sum(w for _, w in parts.values())
            row["priority"] = round(sum(s*w for s, w in parts.values()) / total, 4) if total else None
            row["missing_metrics"] = missing
            row["effective_weights"] = {n: round(w/total, 4) for n, (_, w) in parts.items()} if total else {}
        group.sort(key=lambda x: x["priority"] if x["priority"] is not None else -1, reverse=True)
    return {"mode": pack.get("mode", "missing"), "synthetic": pack.get("synthetic", False),
            "method": "Relevance gate; within-market/language normalized weighted opportunity; missing metrics reweighted",
            "weights": weights, "groups": [{"marketplace": m, "language": l, "keywords": r} for (m, l), r in groups.items()],
            "excluded": excluded, "market_validated": research_valid(pack)}


def image_plan(request):
    errors = check_product(request)
    refs = request.get("reference_assets", [])
    own = [r for r in refs if r["role"] == "product"]
    if not own:
        errors.append(issue("missing_product_photo", "$/reference_assets", "A target product reference is required"))
    facts = confirmed_facts(request)
    dimensions = [f for f in facts.values() if f["key"] in {"dimensions", "width", "height", "depth", "diameter", "length"}]
    sources = {s["id"] for s in request["product"]["sources"]}
    plans, seen = [], set()
    languages = request.get("languages", ["en"])
    for n, slot in enumerate(request.get("image_requirements", [])):
        if slot["id"] in seen:
            errors.append(issue("duplicate_slot", f"$/image_requirements/{n}", "Image slot id must be unique"))
        seen.add(slot["id"])
        kind = slot["type"]
        width, height = IMAGE_TYPES[kind]
        langs = ["none"] if kind == "main" else languages
        for lang in langs:
            sid = slot["id"] + ("" if lang == "none" else "_" + lang)
            blockers = []
            if not own:
                blockers.append("missing_product_photo")
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", slot["id"]):
                blockers.append("unsafe_slot_id")
            if not slot.get("fact_ids") or not set(slot["fact_ids"]).issubset(facts):
                blockers.append("missing_confirmed_slot_facts")
            if kind in {"size", "a_plus_size"} and not dimensions:
                blockers.append("missing_confirmed_dimensions")
            if kind == "a_plus_comparison" and slot.get("comparison_scope") != "same_brand":
                blockers.append("a_plus_requires_same_brand_comparison")
            if kind in {"comparison", "a_plus_comparison"} and (not slot.get("comparison_evidence_ids") or not set(slot["comparison_evidence_ids"]).issubset(sources)):
                blockers.append("missing_comparison_evidence")
            if kind == "a_plus_steps" and not slot.get("steps"):
                blockers.append("missing_confirmed_steps")
            plans.append({"id": sid, "slot_id": slot["id"], "type": kind, "language": lang,
                          "width": width, "height": height,
                          "state": "blocked" if blockers else "ready",
                          "blockers": blockers, "objective": slot.get("objective", ""),
                          "reference_ids": [r["id"] for r in own],
                          "fact_ids": slot.get("fact_ids", []),
                          "copy": "" if kind == "main" else slot.get("copy", {}).get(lang, ""),
                          "prompt": "", "revision": 1})
    return {"schema_version": "1.0", "module": "image-suite", "sku_id": request["product"]["sku_id"],
            "input_sha256": digest(request), "engine": "host_builtin", "images": plans,
            "issues": errors, "generation_executed": False}


def image_technical_review(request, plan, manifest):
    from PIL import Image
    errors, rows = binding_errors(request, manifest) + binding_errors(request, plan), []
    planned = {x["id"]: x for x in plan["images"]}
    seen = set()
    for item in manifest.get("images", []):
        iid = item["id"]
        row_errors = []
        if iid in seen or iid not in planned:
            errors.append(issue("unexpected_image", "$/images", "Duplicate or unknown image: " + iid))
            continue
        seen.add(iid)
        spec = planned[iid]
        if spec["state"] == "blocked":
            row_errors.append(issue("blocked_slot", iid, "Required source information is missing"))
        try:
            with Image.open(item["path"]) as im:
                im.load()
                size, mode = list(im.size), im.mode
                if size != [spec["width"], spec["height"]]:
                    row_errors.append(issue("pixel_size", iid, f"Actual {size}; expected {[spec['width'], spec['height']]}"))
                if mode not in {"RGB", "RGBA"}:
                    row_errors.append(issue("color_mode", iid, "Use RGB/RGBA"))
        except (OSError, ValueError) as exc:
            size, mode = None, None
            row_errors.append(issue("unreadable_image", iid, str(exc)))
        visual = item.get("visual_review", {})
        if visual.get("state") != "pass" or not visual.get("reviewer") or not visual.get("notes"):
            row_errors.append(issue("visual_review_pending", iid, "A real visual review with reviewer and observations is required", "warning"))
        row_errors.extend(visual.get("issues", []))
        rows.append({"id": iid, "path": item["path"], "pixels": size, "mode": mode, "issues": row_errors,
                     "status": "revise" if any(e["severity"] == "error" for e in row_errors) else ("candidate" if row_errors else "keep")})
        errors.extend(row_errors)
    for iid, spec in planned.items():
        if iid not in seen:
            severity = "warning" if spec["state"] == "blocked" else "error"
            errors.append(issue("missing_image", iid, "Blocked source slot" if severity == "warning" else "Planned image missing", severity))
    complete = all(i in seen and s["state"] != "blocked" for i, s in planned.items())
    qa = qa_result(errors)
    if qa["gate"] == "pass" and (not complete or any(x["status"] == "candidate" for x in rows)):
        qa["gate"] = "pending_review"
    return {**qa, "images": rows, "complete": complete}


def archive_image(plan, image_id, source, out_dir, parent_asset=None):
    from PIL import Image
    selected = [x for x in plan["images"] if x["id"] == image_id]
    if not selected or selected[0]["state"] == "blocked":
        raise ValueError("Unknown or blocked image slot")
    spec = selected[0]
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", image_id):
        raise ValueError("Unsafe image id")
    with Image.open(source) as im:
        im.load()
        pixels = list(im.size)
        suffix = "." + (im.format or "png").lower().replace("jpeg", "jpg")
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    revision = 1
    while (out / f"{image_id}_v{revision:03d}{suffix}").exists() or (out / f"{image_id}_v{revision:03d}.json").exists():
        revision += 1
    target = out / f"{image_id}_v{revision:03d}{suffix}"
    with Path(source).open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    record = {"id": image_id, "path": str(target.resolve()), "revision": revision,
              "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "parent_asset": parent_asset,
              "pixels": pixels, "expected_pixels": [spec["width"], spec["height"]],
              "size_pass": pixels == [spec["width"], spec["height"]], "human_approval": "pending"}
    write_new(out / f"{image_id}_v{revision:03d}.json", record)
    return record


def render_report(module, request, result, qa):
    esc = lambda x: html.escape(str(x), quote=True)
    rows = []
    if module == "selling":
        for p in result.get("selling_points", []):
            rows.append(f"<article><h2>{esc(p['theme'])}</h2><p>{esc(p['text'])}</p><p class='muted'>事实 {esc(', '.join(p['fact_ids']))}</p></article>")
    elif module == "listing":
        research = keyword_strategy(request)
        rows.append("<h2>研究与埋词策略</h2><p>数据模式：" + esc(research["mode"]) + "；市场验证：" + esc(research["market_validated"]) + "</p>")
        if research["synthetic"]:
            rows.append("<p class='notice'>合成测试数据，不代表真实市场。</p>")
        for group in research["groups"]:
            rows.append("<h3>" + esc(group["marketplace"] + " / " + group["language"]) + "</h3><table><tr><th>关键词</th><th>搜索量</th><th>相关性</th><th>机会分</th><th>缺项</th><th>来源</th></tr>")
            for k in group["keywords"]:
                rows.append("<tr>" + "".join("<td>" + esc(x) + "</td>" for x in [k["term"], k.get("volume", "未返回"), k["relevance"], k["priority"], ", ".join(k["missing_metrics"]), ", ".join(k["source_ids"])]) + "</tr>")
            rows.append("</table>")
        rows.append("<h2>策略</h2>")
        for s in request["strategies"]:
            rows.append(f"<p><strong>{esc(s['id'])} {esc(s['name'])}</strong> {esc(s['focus'])}</p>")
        for v in result.get("listing_variants", []):
            rows.append(f"<article><h2>{esc(v['marketplace'])} / {esc(v['language'])} / {esc(v['strategy_id'])}</h2><h3>{esc(v['title'])}</h3><ol>")
            rows.extend(f"<li><strong>{esc(b['theme'])}</strong> {esc(b['text'])}</li>" for b in v["bullets"])
            rows.append(f"</ol><p>{esc(v['description'])}</p><p class='muted'>Search terms: {esc(v.get('search_terms', ''))}</p>")
            rows.append("<table><tr><th>关键词</th><th>标题</th><th>五点</th><th>详情</th><th>后台</th></tr>")
            for group in research["groups"]:
                if (group["marketplace"], group["language"]) != (v["marketplace"], v["language"]):
                    continue
                for k in group["keywords"]:
                    term = norm(k["term"])
                    fields = [v["title"], " ".join(b["text"] for b in v["bullets"]), v["description"], v.get("search_terms", "")]
                    rows.append("<tr><td>" + esc(k["term"]) + "</td>" + "".join("<td>" + ("✓" if term in norm(f) else "—") + "</td>" for f in fields) + "</tr>")
            rows.append("</table></article>")
    rows.append("<h2>质量检查</h2><p>机械检查：" + esc(qa["gate"]) + "；语义复核与人工确认仍需完成。</p><ul>")
    rows.extend("<li>" + esc(e["severity"] + " " + e["path"] + " " + e["message"]) + "</li>" for e in qa["issues"])
    rows.append("</ul><h2>来源</h2><ul>")
    for source in request.get("product", {}).get("sources", []) + request.get("research", {}).get("sources", []):
        rows.append("<li>" + esc(source) + "</li>")
    rows.append("</ul>")
    title = "nfwl 卖点测试报告" if module == "selling" else "nfwl Listing 分析与文案"
    return "<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>" + title + "</title><style>body{font:16px/1.7 system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 24px;color:#172332}article{border-top:1px solid #ccd4de;margin:30px 0;padding-top:12px}table{border-collapse:collapse;width:100%;margin:16px 0}th,td{border:1px solid #ccd4de;padding:8px;text-align:left;overflow-wrap:anywhere}.muted{color:#5a6573}.notice{color:#974000}li{margin:8px 0}</style><h1>" + title + "</h1><p>SKU: " + esc(request["product"]["sku_id"]) + " · 草稿，非人工定稿</p>" + "".join(rows) + "</html>"


def import_keywords(path, provider, marketplace, language, synthetic=False):
    p = Path(path)
    if p.suffix.lower() == ".json":
        data = read_json(p)
        raw = data if isinstance(data, list) else data["keywords"]
    else:
        with p.open(encoding="utf-8-sig", newline="") as f:
            sample = f.read(4096); f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
            except csv.Error:
                dialect = csv.excel
            raw = list(csv.DictReader(f, dialect=dialect))
    aliases = {"term": ["term", "keyword", "关键词"], "volume": ["volume", "search_volume", "月搜索量", "搜索量"],
               "purchase_rate": ["purchase_rate", "购买率"], "cpc": ["cpc", "CPC", "建议竞价"],
               "spr": ["spr", "SPR"], "relevance": ["relevance", "相关性"]}
    sid = "export-" + hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    keywords = []
    for n, item in enumerate(raw):
        row = {"marketplace": marketplace, "language": language, "source_ids": [sid]}
        for key, names in aliases.items():
            value = next((item[k] for k in names if k in item and item[k] not in {"", None}), None)
            if key == "term":
                row[key] = str(value or "").strip()
            elif value is not None:
                # Percentages carry explicit units. Locale commas are not silently guessed.
                s = str(value).strip()
                row[key] = float(s[:-1])/100 if s.endswith("%") else float(s)
                if not math.isfinite(row[key]) or row[key] < 0 or (key in {"purchase_rate", "relevance"} and row[key] > 1):
                    raise ValueError(f"Row {n+1}: {key} outside limits")
            else:
                row[key] = None
        if not row["term"]:
            raise ValueError(f"Row {n+1}: keyword missing")
        if row["relevance"] is None:
            row["relevance"] = 0  # unreviewed, excluded from scoring until Agent reviews
        keywords.append(row)
    return {"mode": "test_fixture" if synthetic else "export", "synthetic": synthetic,
            "sources": [{"id": sid, "provider": provider, "file": p.name,
                         "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                         "imported_at": datetime.now(timezone.utc).isoformat()}], "keywords": keywords}


def cli(skill_dir=None):
    skill_dir = Path(skill_dir or Path(__file__).resolve().parents[1])
    parser = argparse.ArgumentParser(description="nfwl skill artifact helpers; creative work is performed by the host Agent")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["prepare", "strategy", "plan-images"]:
        p = sub.add_parser(name); p.add_argument("--input", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("validate"); p.add_argument("--input", required=True); p.add_argument("--result", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("report"); p.add_argument("--input", required=True); p.add_argument("--result", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("import-keywords"); p.add_argument("--file", required=True); p.add_argument("--provider", required=True); p.add_argument("--marketplace", required=True); p.add_argument("--language", required=True); p.add_argument("--synthetic", action="store_true"); p.add_argument("--output", required=True)
    p = sub.add_parser("check-images"); p.add_argument("--input", required=True); p.add_argument("--plan", required=True); p.add_argument("--manifest", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("archive-image"); p.add_argument("--plan", required=True); p.add_argument("--id", required=True); p.add_argument("--source", required=True); p.add_argument("--out-dir", required=True); p.add_argument("--parent-asset")
    args = parser.parse_args()
    try:
        if args.command == "import-keywords":
            value = import_keywords(args.file, args.provider, args.marketplace, args.language, args.synthetic)
        elif args.command == "archive-image":
            value = archive_image(read_json(args.plan), args.id, args.source, args.out_dir, args.parent_asset)
            print(json.dumps(value, ensure_ascii=False)); return 0
        else:
            request = read_json(args.input)
            contract_errors = schema_errors(request, read_json(skill_dir / "references/input.schema.json"))
            if contract_errors:
                write_new(args.output, {"gate": "block", "issues": contract_errors})
                return 2
            if args.command == "prepare":
                value = prepare(request)
            elif args.command == "strategy":
                value = keyword_strategy(request)
            elif args.command == "plan-images":
                value = image_plan(request)
            elif args.command == "check-images":
                value = image_technical_review(request, read_json(args.plan), read_json(args.manifest))
            else:
                result = read_json(args.result)
                result_errors = schema_errors(result, read_json(skill_dir / "references/output.schema.json"))
                rules = rules_for(skill_dir)
                module = "selling" if skill_dir.name == "nfwl-selling-points" else "listing"
                qa = qa_result(result_errors) if result_errors else (selling_review(request, result, rules) if module == "selling" else listing_review(request, result, rules))
                value = render_report(module, request, result, qa) if args.command == "report" and not result_errors else qa
        write_new(args.output, value)
        if isinstance(value, dict) and (value.get("gate") in {"revise", "block"} or any(e.get("severity") == "error" for e in value.get("issues", []))):
            return 2
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"nfwl: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(cli())
