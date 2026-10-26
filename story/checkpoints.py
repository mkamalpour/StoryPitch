"""Bounded read-only checkpoint comparisons; no generation or restoration."""
import json


def compare_worlds(current, saved, max_fields=50, preview_chars=600):
    if not isinstance(current, dict) or not isinstance(saved, dict):
        raise ValueError('Both story states must be JSON objects.')
    changed = [key for key in sorted(set(current) | set(saved))
               if (key in current) != (key in saved) or current.get(key) != saved.get(key)]
    fields = []
    for key in changed[:max_fields]:
        row = dict(field=key, current_present=key in current, saved_present=key in saved)
        for side, state in [('current', current), ('saved', saved)]:
            text = json.dumps(state.get(key), ensure_ascii=False, sort_keys=True)
            row[side] = text[:preview_chars]
            row[side + '_truncated'] = len(text) > preview_chars
        fields.append(row)
    return dict(changed_field_count=len(changed), fields=fields,
                omitted_field_count=max(0, len(changed) - len(fields)),
                scope='Top-level story state fields; long values are previewed, not altered.')
