import re
import collections


def make_preferred_filter(args, types):
    args = [v for v in args if v[0] == 'prefer']
    if not args:
        return lambda _: False
    return make_filter(args=args, types=types)


def make_filter(args, types):
    filters = tuple(generate_field_filters(args=args, types=types))
    if not filters:
        return lambda _: True
    def impl(value):
        includes = dict()
        excludes = dict()
        for include, field, field_filter in filters:
            field_result = bool(field_filter(getattr(value, field)))
            if include:
                includes[field] = field_result or bool(includes.get(field))
            else:
                excludes[field] = field_result or bool(excludes.get(field))
        return (not includes or any(includes.values())) and not (excludes and any(excludes.values()))
    return impl


def generate_field_filters(args, types):
    present = set()
    for filter_type, field, pattern in args:
        assert filter_type in ('include', 'exclude', 'prefer')
        if (filter_type, field, pattern) in present:
            continue
        present.add((filter_type, field, pattern))
        field_filter = make_typed_field_filter(field_type=types[field], pattern=pattern)
        if field_filter:
            yield filter_type in ('include', 'prefer'), field, field_filter


def make_typed_field_filter(field_type, pattern):
    if field_type == int:
        pattern = int(pattern)
        return lambda value: value == pattern
    elif field_type == str:
        regex = re.compile(pattern)
        return lambda value: re.search(regex, value)
    elif isinstance(field_type, list):
        f = make_typed_field_filter(field_type[0], pattern)
        return lambda value: any(v for v in value if f(v))
    return None
