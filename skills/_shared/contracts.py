"""Contract source used to build portable resources for the three main skills."""
import copy

S = {"type": "string", "minLength": 1}
STRINGS = {"type": "array", "items": S}
def obj(properties, required=None, extra=False):
    return {"type": "object", "properties": properties, "required": list(properties) if required is None else required, "additionalProperties": extra}
def arr(items, minimum=0):
    return {"type": "array", "items": items, "minItems": minimum}

SOURCE = obj({"id": S, "type": {"enum": ["user", "manual", "measurement", "manufacturer", "test_fixture"]}, "ref": S})
FACT = obj({"id": S, "key": S, "value": {}, "unit": {"type": "string"},
            "status": {"enum": ["confirmed", "needs_review", "conflict", "missing", "not_applicable"]},
            "source_ids": STRINGS, "allowed_claims": STRINGS},
           ["id", "key", "value", "status", "source_ids"])
RESTRICTION = obj({"message": S, "patterns": STRINGS})
PRODUCT = obj({"sku_id": S, "name": S, "category": S, "facts": arr(FACT, 1), "sources": arr(SOURCE, 1),
               "restrictions": arr(RESTRICTION), "competitor_brands": STRINGS, "sample_kind": {"enum": ["real", "synthetic"]}},
              ["sku_id", "name", "category", "facts", "sources"])
POINT = obj({"id": S, "theme": S, "dimension": {"enum": ["pain_point", "function", "material", "operation", "accessory", "extra"]},
             "text": S, "pain_point": S, "feature": S, "benefit": S, "fact_ids": {**STRINGS, "minItems": 1},
             "status": {"enum": ["draft", "confirmed"]}},
            ["id", "theme", "dimension", "text", "pain_point", "feature", "benefit", "fact_ids"])
KEYWORD = obj({"term": S, "marketplace": S, "language": S, "relevance": {"type": "number", "minimum": 0, "maximum": 1},
               "volume": {"type": ["number", "null"], "minimum": 0}, "purchase_rate": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
               "spr": {"type": ["number", "null"], "minimum": 0}, "cpc": {"type": ["number", "null"], "minimum": 0},
               "source_ids": STRINGS}, ["term", "marketplace", "language", "relevance", "source_ids"])
RESEARCH = obj({"mode": {"enum": ["live", "export", "missing", "test_fixture"]}, "synthetic": {"type": "boolean"},
                "sources": arr(obj({"id": S, "provider": S}, ["id", "provider"], True)), "keywords": arr(KEYWORD),
                "competitors": arr({"type": "object"}), "gaps": STRINGS}, ["mode", "sources", "keywords"])
STRATEGY = obj({"id": S, "name": S, "focus": S, "primary_keywords": STRINGS}, ["id", "name", "focus"])
TARGET = obj({"marketplace": S, "language": {"enum": ["en", "de", "fr", "es", "it", "ja"]}})
BASE = {"schema_version": {"const": "1.0"}, "product": PRODUCT, "instruction": {"type": "string"}}
SELLING_INPUT = obj({**BASE, "language": S, "desired_count": {"type": "integer", "minimum": 1, "maximum": 12},
                     "competitor_notes": STRINGS, "voc": arr({"type": "object"})}, ["schema_version", "product", "language"])
SELLING_OUTPUT = obj({"schema_version": {"const": "1.0"}, "module": {"const": "selling-points"}, "sku_id": S,
                      "input_sha256": S, "selling_points": arr(POINT, 1), "gaps": STRINGS},
                     ["schema_version", "module", "sku_id", "input_sha256", "selling_points", "gaps"])
BULLET = obj({"theme": S, "text": S, "selling_point_ids": {**STRINGS, "minItems": 1}})
VARIANT = obj({"id": S, "marketplace": S, "language": S, "strategy_id": S, "title": S,
               "bullets": arr(BULLET), "description": S, "search_terms": {"type": "string"},
               "evidence_map": {"type": "object", "additionalProperties": STRINGS},
               "strategy_rationale": S},
              ["id", "marketplace", "language", "strategy_id", "title", "bullets", "description", "search_terms", "evidence_map", "strategy_rationale"])
LISTING_INPUT = obj({**BASE, "selling_points": arr(POINT, 1), "targets": arr(TARGET, 1), "strategies": arr(STRATEGY, 1),
                     "research": RESEARCH, "field_limits": {"type": "object"},
                     "keyword_weights": obj({k: {"type": "number", "minimum": 0, "maximum": 1}
                                             for k in ["volume", "relevance", "purchase_rate", "spr", "cpc"]}, [], False)},
                    ["schema_version", "product", "selling_points", "targets", "strategies", "research"])
LISTING_OUTPUT = obj({"schema_version": {"const": "1.0"}, "module": {"const": "listing"}, "sku_id": S,
                      "input_sha256": S, "listing_variants": arr(VARIANT, 1), "gaps": STRINGS})
ASSET = obj({"id": S, "path": S, "role": {"enum": ["product", "style", "competitor", "dimension", "usage"]}})
TYPES = ["main", "size", "detail", "feature", "comparison", "lifestyle", "a_plus_hero", "a_plus_size", "a_plus_detail", "a_plus_steps", "a_plus_comparison", "a_plus_scene"]
SLOT = obj({"id": S, "type": {"enum": TYPES}, "objective": S, "fact_ids": STRINGS,
            "copy": {"type": "object"}, "steps": STRINGS, "comparison_scope": {"enum": ["same_brand", "alternative"]},
            "comparison_evidence_ids": STRINGS}, ["id", "type", "objective", "fact_ids"])
IMAGE_INPUT = obj({**BASE, "reference_assets": arr(ASSET, 1), "languages": {"type": "array", "items": S, "minItems": 1, "uniqueItems": True},
                   "image_requirements": arr(SLOT, 1), "visual_identity": {"type": "string"}, "style": {"type": "string"}},
                  ["schema_version", "product", "reference_assets", "languages", "image_requirements"])
IMAGE_RESULT = obj({"id": S, "path": S, "revision": {"type": "integer", "minimum": 1},
                    "visual_review": obj({"state": {"enum": ["pass", "revise", "pending"]}, "reviewer": S,
                                          "notes": S, "issues": arr({"type": "object"})}, ["state"])}, ["id", "path", "revision"])
IMAGE_OUTPUT = obj({"schema_version": {"const": "1.0"}, "module": {"const": "image-suite"}, "sku_id": S,
                    "input_sha256": S, "images": arr(IMAGE_RESULT), "gaps": STRINGS})
SCHEMAS = {"nfwl-selling-points": (SELLING_INPUT, SELLING_OUTPUT),
           "nfwl-listing": (LISTING_INPUT, LISTING_OUTPUT),
           "nfwl-image-suite": (IMAGE_INPUT, IMAGE_OUTPUT)}
for pair in SCHEMAS.values():
    for schema in pair:
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"

RULES = {
 "version": "1.0.0", "authority": "Customer attachments; stricter site/category rules may be added with source/version",
 "title_max_chars": 75, "title_forbidden_chars": "!?_{}^~¬¦$！？，【】", 
 "forbidden_terms": ["best", "most", "permanent", "forever", "顶级", "最好", "永久", "杀菌", "治疗", "消炎", "治病", "理疗",
                     "free shipping", "limited time", "coupon", "clearance", "full refund", "money back", "leave a review", "five-star", "很多人喜欢",
                     "guaranteed", "100% safe", "免运费", "优惠券", "全额退款",
                     "cures", "treats disease", "anti-inflammatory", "sterilizes",
                     "beste", "besten", "für immer", "heilt", "meilleur", "meilleure", "pour toujours",
                     "mejor", "para siempre", "migliore", "per sempre", "最高", "治療"],
 "claim_patterns": {
   r"\b304\b": "304 steel grade", r"\b(?:FDA|LFGB|ETL|UL|CE|FCC)\b": "certification",
   r"\bIP\d{2}\b": "ingress rating", r"\bwaterproof\b|防水": "waterproofing",
   r"\brustproof\b|永不生锈": "rustproofing", r"\bautomatic(?:ally)?\b|自动": "automatic function",
   r"\btimer\b|定时": "timer", r"\bfood[ -]grade\b|食品级": "food grade",
   r"\bsterili[sz]|\bantibacterial\b": "medical/antimicrobial effect",
   r"\bwarranty\b|质保": "warranty",
 },
 "stop_words": {
  "en": ["a", "an", "the", "and", "or", "of", "for", "to", "in", "with"],
  "de": ["der", "die", "das", "ein", "eine", "und", "oder", "für", "mit", "in"],
  "fr": ["le", "la", "les", "de", "des", "et", "pour", "avec"],
  "es": ["el", "la", "los", "de", "y", "para", "con"],
  "it": ["il", "la", "di", "e", "per", "con"]
 }
}
