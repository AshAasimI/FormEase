from formease.models import FormField


def order_fields(fields: list[FormField]) -> list[FormField]:
    """Sort fields into natural form-filling order.

    Policy: page index first, then top-to-bottom (quantised into rows
    with 20px tolerance to handle slight misalignment), then left-to-right.
    Field IDs are reassigned after ordering.
    """
    def sort_key(f: FormField):
        x1, y1, x2, y2 = f.label_bbox
        row = y1 // 20
        return (f.page_index, row, x1)

    ordered = sorted(fields, key=sort_key)

    # Reassign sequential field IDs
    for i, f in enumerate(ordered):
        f.field_id = f"f{i:03d}"

    return ordered
