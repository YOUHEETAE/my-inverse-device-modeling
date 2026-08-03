from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any


# Internal references remain useful for validation and session persistence, but
# they are implementation details and must never appear in learner-facing prose.
_INTERNAL_REFERENCE = re.compile(
    r"(?ix)"
    r"(?:\bevidence[_\s-]?ids?\b\s*[:=]?)"
    r"|(?<![\w])(?:metric|experiment):[a-z0-9_.-]+"
    r"|(?<![\w])(?:ev|fsf|fsc)_[a-z0-9_]+"
)

_QUANTITY_LABELS = {
    "vth": "문턱전압(Vth)",
    "vth_low": "낮은 Drain 전압의 문턱전압",
    "vth_high": "높은 Drain 전압의 문턱전압",
    "ion": "온 전류(Ion)",
    "ioff": "오프 전류(Ioff)",
    "ion_ioff_ratio": "Ion/Ioff 비",
    "ss": "Subthreshold swing(SS)",
    "dibl": "DIBL",
    "gm": "트랜스컨덕턴스(gm)",
    "gm_max": "최대 트랜스컨덕턴스",
    "gds": "출력 컨덕턴스(gds)",
    "ron": "온 저항(Ron)",
    "lambda_clm": "채널 길이 변조 계수",
    "potential": "전위 분포",
    "electric_field": "전계 분포",
    "electron_density": "전자 농도 분포",
    "hole_density": "정공 농도 분포",
}

_PUBLIC_TEXT_TRANSLATION = str.maketrans({
    "\u00a0": " ",   # no-break space
    "\u2007": " ",   # figure space
    "\u202f": " ",   # narrow no-break space
    "\u200b": "",    # zero-width space
    "\ufeff": "",    # zero-width no-break space / BOM
    "\u2010": "-",
    "\u2011": "-",   # non-breaking hyphen
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u2022": "-",   # bullet
    "\u25aa": "-",
    "\u25ab": "-",
    "\u25a0": "-",
    "\u25a1": "-",
    "\ufffd": "?",
})


def normalize_public_text(value: Any) -> str:
    """Normalize provider typography to glyphs reliably rendered by Tk."""
    text = unicodedata.normalize("NFC", str(value or ""))
    # Some JSON-capable models return a second layer of escaped line breaks
    # inside the decoded answer string. Render those as real lines instead of
    # exposing the two characters ``\`` and ``n`` to the learner.
    text = re.sub(r"\\r\\n|\\n", "\n", text)
    text = re.sub(r"\bcm\s*[⁻−-]\s*³", "cm^-3", text)
    text = text.translate(
        _PUBLIC_TEXT_TRANSLATION
    )
    text = "".join(
        character
        for character in text
        if character in "\n\t" or unicodedata.category(character) != "Cc"
    )
    return re.sub(r"[ \t]+", " ", text).strip()


def find_internal_references(text: str) -> tuple[str, ...]:
    """Return machine references accidentally embedded in public prose."""
    return tuple(dict.fromkeys(match.group(0) for match in _INTERNAL_REFERENCE.finditer(text)))


def validate_public_answer_text(text: str) -> None:
    if find_internal_references(text):
        raise ValueError("internal_evidence_reference_exposed")


def evidence_display_label(reference_id: str, *, quantity: str | None = None, region: str | None = None) -> str:
    """Create a stable learner-facing label without exposing the machine ID."""
    if reference_id == "experiment:conditions":
        return "실험 조건"
    normalized = str(quantity or "").strip().lower()
    if not normalized and reference_id.startswith("metric:"):
        normalized = reference_id.split(":", 1)[1].strip().lower()
    if not normalized:
        lowered = reference_id.lower()
        normalized = next(
            (name for name in sorted(_QUANTITY_LABELS, key=len, reverse=True) if name in lowered),
            "",
        )
    quantity_label = _QUANTITY_LABELS.get(normalized, normalized.replace("_", " ").strip())
    if quantity_label:
        return f"{region}의 {quantity_label} 관찰" if region else f"{quantity_label} 관찰"
    return f"{region} 영역 관찰" if region else "현재 결과의 검증된 관찰"


@dataclass(frozen=True)
class EvidenceReference:
    reference_id: str
    display_label: str
    source: str | None = None
    quantity: str | None = None
    region: str | None = None


@dataclass(frozen=True)
class GroundedAnswerContract:
    """Common internal boundary for Case, I-V, and Field explanations.

    Legacy automatic explanations are retained in ``summary`` until the
    domain-specific interpreters populate observations and interpretations in
    later stages. Evidence references are deliberately separate from prose.
    """

    analysis_type: str
    summary: tuple[str, ...] = ()
    observations: tuple[str, ...] = ()
    interpretations: tuple[str, ...] = ()
    tradeoffs: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    schema_version: str = "1.0"

    @classmethod
    def from_legacy_response(
        cls,
        payload: dict[str, Any],
        response: dict[str, list[str]],
    ) -> "GroundedAnswerContract":
        public_text = " ".join(
            sentence
            for section in ("descriptions", "comparisons", "tradeoffs", "cautions")
            for sentence in response.get(section, [])
        )
        validate_public_answer_text(public_text)
        references = []
        for item in payload.get("evidence", []):
            if not item.get("eligible_for_output", True):
                continue
            reference_id = str(item.get("evidence_id", "")).strip()
            if not reference_id:
                continue
            references.append(EvidenceReference(
                reference_id=reference_id,
                display_label=evidence_display_label(
                    reference_id,
                    quantity=str(item.get("quantity", "") or ""),
                    region=str(item.get("region", "") or "") or None,
                ),
                source=str(item.get("source_type", "") or "") or None,
                quantity=str(item.get("quantity", "") or "") or None,
                region=str(item.get("region", "") or "") or None,
            ))
        has_explicit_interpretation = bool(
            (payload.get("interpretation") or {}).get("mechanism_chains")
        )
        return cls(
            analysis_type=str(payload.get("analysis_type", "unknown")),
            summary=tuple(response.get("descriptions", ())),
            observations=(
                ()
                if has_explicit_interpretation
                else tuple(response.get("comparisons", ()))
            ),
            interpretations=(
                tuple(response.get("comparisons", ()))
                if has_explicit_interpretation
                else ()
            ),
            tradeoffs=tuple(response.get("tradeoffs", ())),
            limitations=tuple(response.get("cautions", ())),
            evidence=tuple(references),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
