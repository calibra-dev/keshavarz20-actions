#!/usr/bin/env python3
import importlib.util
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("qe15", os.path.join(ROOT, "engine_v15.py"))
v15 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v15)
q = v15.q

orig_family = q.b.family
orig_fitting_subtype = q.fitting_subtype


def n(value):
    return q.b.norm(str(value or ""))


def _is_flange_name(p):
    name = n(p.get("name"))
    return n("فلنج") in name or n("فلنچ") in name


def family_v16(p):
    # Common catalog spelling variants: both «فلنج» and «فلنچ» are fittings.
    # Resolve this narrow product identity before broad PE-pipe tokens such as «لوله».
    if _is_flange_name(p):
        return "fitting"
    return orig_family(p)


def fitting_subtype_v16(p):
    if _is_flange_name(p):
        return "flange"
    return orig_fitting_subtype(p)


q.b.family = family_v16
q.fitting_subtype = fitting_subtype_v16


def main():
    q.main()


if __name__ == "__main__":
    main()
