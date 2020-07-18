import collections

from sigame_tools.filters import (
    make_typed_field_filter
)


def make_get_weight(args, types):
    filters = tuple(generate_field_filters(args=args, types=types))
    if not filters:
        return lambda _: 1
    weights = dict()
    def impl(value):
        result = weights.get(value)
        if result is None:
            by_field = collections.defaultdict(list)
            for field, field_filter, weight in filters:
                by_field[field].append(weight if field_filter(getattr(value, field)) else 1)
            for field in types.keys():
                v = by_field[field]
                if not v:
                    v.append(1)
            result = sum(sum(by_field[t]) / len(by_field[t]) if t in by_field else 1 for t in types) / len(types)
            weights[value] = result
        return result
    return impl


def generate_field_filters(args, types):
    for field, pattern, weight in args:
        field_filter = make_typed_field_filter(field_type=types[field], pattern=pattern)
        if field_filter:
            yield field, field_filter, weight
