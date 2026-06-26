"""Template compatibility checks against explicit user constraints."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.spl.template_registry import SplTemplateDefinition, get_spl_template
from app.spl.template_slot_bindings import accepted_slots_for_template
from app.spl.user_constraint_bindings import UserConstraintBindings


def _draft_family_spl(family_id: str | None) -> str:
    if not family_id:
        return ""
    try:
        from app.spl.draft_preview import _family_by_id

        family = _family_by_id(family_id)
        return family.draft_spl if family is not None else ""
    except Exception:
        return ""


@dataclass
class TemplateCompatibilityResult:
    compatible: bool
    incompatible_reasons: list[str] = field(default_factory=list)
    use_user_bound_skeleton: bool = False
    template_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "compatible": self.compatible,
            "incompatible_reasons": list(self.incompatible_reasons),
            "use_user_bound_skeleton": self.use_user_bound_skeleton,
            "template_id": self.template_id,
        }


_FAMILY_PROTOCOL_BROADEN = {
    "scada_dnp3_modbus_write": ("dnp3", "modbus"),
}


def check_template_compatibility(
    template_id: str | None,
    bindings: UserConstraintBindings,
    *,
    template: SplTemplateDefinition | None = None,
    family_id: str | None = None,
) -> TemplateCompatibilityResult:
    resolved = template or (get_spl_template(template_id) if template_id else None)
    reasons: list[str] = []
    spl_text = (resolved.spl_text if resolved else "") or _draft_family_spl(family_id) or ""
    family = family_id or (resolved.template_id if resolved else None)

    if bindings.explicit_indexes:
        for index in bindings.explicit_indexes:
            if spl_text and f"index={index}" not in spl_text.lower():
                if re.search(r"index=<", spl_text, re.I):
                    reasons.append(f"replaces_user_index:{index}")

    if bindings.explicit_protocols and len(bindings.explicit_protocols) == 1:
        user_protocol = bindings.explicit_protocols[0].lower()
        if family in _FAMILY_PROTOCOL_BROADEN:
            broad = _FAMILY_PROTOCOL_BROADEN[family]
            if user_protocol in broad:
                siblings = [p for p in broad if p != user_protocol]
                for sibling in siblings:
                    if sibling in spl_text.lower():
                        reasons.append(f"broadens_protocol_without_request:{sibling}")

    accepted_slots = accepted_slots_for_template(family)

    if (
        bindings.explicit_function_codes
        and "function_code" in accepted_slots
        and family == "scada_dnp3_modbus_write"
    ):
        reasons.append("drops_explicit_function_codes")

    if bindings.explicit_directionality.get("unexpected_ip_direction") == "destination":
        if "engineering_workstation_cidr" in spl_text and "dest" not in spl_text.lower():
            reasons.append("reverses_unexpected_ip_direction")

    if bindings.explicit_event_codes and resolved and "event_code" in accepted_slots:
        for code in bindings.explicit_event_codes:
            if str(code) not in spl_text:
                reasons.append(f"drops_explicit_event_code:{code}")

    compatible = not reasons
    return TemplateCompatibilityResult(
        compatible=compatible,
        incompatible_reasons=reasons,
        use_user_bound_skeleton=not compatible and bool(bindings.normalized_slots or bindings.explicit_indexes),
        template_id=template_id or family,
    )
