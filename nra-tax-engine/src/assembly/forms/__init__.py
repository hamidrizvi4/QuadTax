"""Per-form populator registry.

Each module under this package exposes a single :func:`compute_field_map`
function that turns a finalized :class:`ReturnStateObject` into a flat
``dict[pdf_field_name, value]``. The dispatcher below reads
``state.forms_required`` and calls the matching populator. The
``form_populator`` module then writes the field-map into the AcroForm
fields of the IRS PDF template.

Adding a new form: implement ``compute_field_map`` in a new module and
register it in :data:`FORM_REGISTRY` below.
"""

from __future__ import annotations

from typing import Callable, Dict

from src.assembly.forms import (
    form_843,
    form_1040nr,
    form_2210,
    form_6251,
    form_8833,
    form_8843,
    form_w7,
    it_203,
    it_203b,
    it_203d,
    schedule_a,
    schedule_nec,
    schedule_oi,
)

FORM_REGISTRY: Dict[str, Callable[..., dict]] = {
    # Federal
    "1040-NR": form_1040nr.compute_field_map,
    "Schedule-OI": schedule_oi.compute_field_map,
    "Schedule-NEC": schedule_nec.compute_field_map,
    "Schedule-A": schedule_a.compute_field_map,
    "8843": form_8843.compute_field_map,
    "8833": form_8833.compute_field_map,
    "843": form_843.compute_field_map,
    "W-7": form_w7.compute_field_map,
    "6251": form_6251.compute_field_map,
    "2210": form_2210.compute_field_map,
    # New York
    "IT-203": it_203.compute_field_map,
    "IT-203-B": it_203b.compute_field_map,
    "IT-203-D": it_203d.compute_field_map,
}


def compute(form_name: str, state) -> dict:
    """Dispatch to the registered populator for ``form_name``.

    Raises:
        KeyError: If ``form_name`` is not registered.
    """
    populator = FORM_REGISTRY[form_name]
    return populator(state)
