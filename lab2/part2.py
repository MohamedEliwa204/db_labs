"""
Relational Algebra Studio
-------------------------
A Streamlit front-end for your own `Relation` class (Relation.py).

Highlights
- JSON / CSV / pasted data, one-click sample dataset, editable tables
- Schema profiler + auto-detected join graph
- Visual query builder (no code needed)
- Sandbox: lecture-style relational algebra expressions (π, σ, ρ, ⨝, γ, ∪, ∩, -),
  human-readable SQL-like conditions without lambdas, step-by-step pipeline trace
- Charts, CSV/JSON export, save results as new tables
- Query history + saved queries, auto-generated operator reference
"""
import ast
import builtins
import csv
import difflib
import inspect
import io
import json
import re
import time
import traceback

import pandas as pd
import streamlit as st

from Relation import Relation

st.set_page_config(page_title="Relational Algebra Studio", page_icon="🧮", layout="wide")

st.markdown(
    """
    <style>
    .hero {padding: 1.1rem 1.4rem; border-radius: 14px; margin-bottom: 1rem;
           background: linear-gradient(120deg, rgba(99,102,241,.18), rgba(236,72,153,.14));
           border: 1px solid rgba(128,128,128,.25);}
    .hero h1 {margin: 0; font-size: 1.9rem;}
    .hero p {margin: .25rem 0 0 0; opacity: .8;}
    </style>
    <div class="hero">
      <h1>🧮 Relational Algebra Studio</h1>
      <p>Load data, build queries visually or in formal lecture notation, and watch every step.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# =============================================================================
# Constants & Sample Data
# =============================================================================
SAMPLE_DATA = {
    "Employee": [
        {"ID": 1, "Name": "Ali", "Salary": 5200, "DeptID": 10, "HireYear": 2019},
        {"ID": 2, "Name": "Sara", "Salary": 7400, "DeptID": 20, "HireYear": 2017},
        {"ID": 3, "Name": "Omar", "Salary": 4300, "DeptID": 10, "HireYear": 2022},
        {"ID": 4, "Name": "Laila", "Salary": 9100, "DeptID": 30, "HireYear": 2015},
        {"ID": 5, "Name": "Youssef", "Salary": 6100, "DeptID": 20, "HireYear": 2020},
        {"ID": 6, "Name": "Mona", "Salary": 5800, "DeptID": 30, "HireYear": 2021},
    ],
    "Department": [
        {"DeptID": 10, "DeptName": "Support", "City": "Cairo"},
        {"DeptID": 20, "DeptName": "Engineering", "City": "Alexandria"},
        {"DeptID": 30, "DeptName": "Finance", "City": "Giza"},
    ],
    "Project": [
        {"ProjID": 100, "Title": "Mobile App", "DeptID": 20, "Budget": 80000},
        {"ProjID": 101, "Title": "Billing v2", "DeptID": 30, "Budget": 45000},
        {"ProjID": 102, "Title": "Help Center", "DeptID": 10, "Budget": 15000},
        {"ProjID": 103, "Title": "Data Lake", "DeptID": 20, "Budget": 120000},
    ],
}

_SAFE_NAMES = [
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int", "isinstance",
    "len", "list", "map", "max", "min", "range", "reversed", "round", "set", "sorted", "str",
    "sum", "tuple", "zip", "True", "False", "None",
]
SAFE_BUILTINS = {n: getattr(builtins, n) for n in _SAFE_NAMES}


# =============================================================================
# Formal Relational Algebra Wrappers (DSL Engine)
# =============================================================================
def _parse_condition(cond_str: str) -> str:
    """Translates SQL-like relational algebra conditions to safe Python expressions[cite: 14]."""
    # Replace single '=' with '==' while preserving '==', '!=', '>=', '<='
    py_cond = re.sub(r'(?<![=<>!])=(?![=])', '==', cond_str)
    # Translate SQL logical operators to Python equivalents[cite: 14]
    py_cond = re.sub(r'\bAND\b', 'and', py_cond, flags=re.IGNORECASE)
    py_cond = re.sub(r'\bOR\b', 'or', py_cond, flags=re.IGNORECASE)
    py_cond = re.sub(r'\bNOT\b', 'not', py_cond, flags=re.IGNORECASE)
    return py_cond


def SELECT(condition_str: str, relation: Relation) -> Relation:
    """Unary SELECT (σ) operation using human-readable conditions[cite: 9, 14]."""
    py_cond = _parse_condition(condition_str)

    def cond_func(row):
        try:
            return bool(eval(py_cond, {"__builtins__": SAFE_BUILTINS}, dict(row)))
        except Exception:
            return False

    return relation.select(cond_func, condition_str)


def PROJECT(attribute_list: list, relation: Relation) -> Relation:
    """Unary PROJECT (π) operation[cite: 9, 17]."""
    return relation.project(attribute_list)


def RENAME(new_relation_name: str, new_columns_map: dict, relation: Relation) -> Relation:
    """Unary RENAME (ρ) operation for relations and attributes[cite: 9, 20]."""
    new_rows = []
    for row in relation.rows:
        new_rows.append({new_columns_map.get(col, col): val for col, val in row.items()})
    return Relation(new_relation_name if new_relation_name else relation.name, new_rows)


def UNION(rel1: Relation, rel2: Relation) -> Relation:
    """Binary UNION (∪) operation from Set Theory[cite: 9, 24]."""
    return rel1.union(rel2)


def INTERSECT(rel1: Relation, rel2: Relation) -> Relation:
    """Binary INTERSECTION (∩) operation from Set Theory[cite: 9, 24]."""
    return rel1.intersect(rel2)


def MINUS(rel1: Relation, rel2: Relation) -> Relation:
    """Binary DIFFERENCE / MINUS (-) operation from Set Theory[cite: 9, 27]."""
    return rel1.difference(rel2)


def PRODUCT(rel1: Relation, rel2: Relation) -> Relation:
    """Binary CARTESIAN PRODUCT (×) operation[cite: 9, 28]."""
    if hasattr(rel1, "product"):
        return rel1.product(rel2)
    # Fallback to theta join with tautological condition if product is not standalone[cite: 32]
    return rel1.join(rel2, lambda r1, r2: True, "cartesian")


def JOIN(condition_str: str, rel1: Relation, rel2: Relation) -> Relation:
    """Binary THETA JOIN (⋈) operation with a human-readable condition[cite: 9, 31, 33]."""
    py_cond = _parse_condition(condition_str)

    def cond_func(r1, r2):
        local_env = {**r1, **r2}
        try:
            return bool(eval(py_cond, {"__builtins__": SAFE_BUILTINS}, local_env))
        except Exception:
            return False

    return rel1.join(rel2, cond_func, condition_str)


def NATURAL_JOIN(rel1: Relation, rel2: Relation) -> Relation:
    """Binary NATURAL JOIN (*) operation evaluating equality of common attributes[cite: 33, 34]."""
    return rel1.natural_join(rel2)


def AGGREGATE(group_by_cols: list, aggregations: list, relation: Relation) -> Relation:
    """AGGREGATE (ℱ / γ) Functions (e.g. SUM, AVERAGE, COUNT, MIN, MAX)[cite: 46, 48]."""
    return relation.aggregate(group_by_cols, aggregations)


# Dictionary exposing operators to the sandbox
RA_DSL = {
    "SELECT": SELECT, "σ": SELECT,
    "PROJECT": PROJECT, "π": PROJECT, "PI": PROJECT,
    "RENAME": RENAME, "ρ": RENAME, "RHO": RENAME,
    "UNION": UNION, "∪": UNION,
    "INTERSECT": INTERSECT, "∩": INTERSECT,
    "MINUS": MINUS, "DIFFERENCE": MINUS,
    "PRODUCT": PRODUCT, "×": PRODUCT, "CARTESIAN_PRODUCT": PRODUCT,
    "JOIN": JOIN, "⋈": JOIN, "THETA_JOIN": JOIN,
    "NATURAL_JOIN": NATURAL_JOIN,
    "AGGREGATE": AGGREGATE, "γ": AGGREGATE, "F": AGGREGATE, "ℱ": AGGREGATE,
}

# =============================================================================
# Session state
# =============================================================================
for _k, _v in {
    "relations": {},
    "history": [],
    "saved": [],
    "builder": {"base": None, "steps": []},
    "last": None,
    "file_sig": None,
    "query_input": "",
}.items():
    st.session_state.setdefault(_k, _v)


# =============================================================================
# Helpers: UI compatibility & Data
# =============================================================================
def show_table(data, **kwargs):
    try:
        st.dataframe(data, width="stretch", **kwargs)
    except TypeError:
        st.dataframe(data, use_container_width=True, **kwargs)


def get_columns(rel):
    cols = getattr(rel, "columns", None)
    if cols:
        return list(cols)
    return list(rel.rows[0].keys()) if getattr(rel, "rows", None) else []


def numeric_cols(rel):
    out = []
    for c in get_columns(rel):
        vals = [r.get(c) for r in rel.rows if r.get(c) is not None]
        if vals and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
            out.append(c)
    return out


def column_profile(rel):
    rows = []
    for c in get_columns(rel):
        vals = [r.get(c) for r in rel.rows]
        present = [v for v in vals if v is not None]
        try:
            lo, hi = min(present), max(present)
        except (TypeError, ValueError):
            lo = hi = None
        rows.append({
            "column": c,
            "type": "/".join(sorted({type(v).__name__ for v in present})) or "—",
            "nulls": len(vals) - len(present),
            "distinct": len({repr(v) for v in present}),
            "min": "" if lo is None else str(lo),
            "max": "" if hi is None else str(hi),
        })
    return rows


def validate_dataset(data):
    if not isinstance(data, dict) or not data:
        raise ValueError("JSON must be an object like {\"Table\": [ {row}, {row} ]}.")
    for name, rows in data.items():
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ValueError(f"Table '{name}' must be a list of row objects.")


def make_relations(data):
    rels = {}
    for raw, rows in data.items():
        name = re.sub(r"\W|^(?=\d)", "_", str(raw))
        rels[name] = Relation(name=name, rows=rows)
    return rels


def ingest(data, replace=False):
    validate_dataset(data)
    new = make_relations(data)
    st.session_state.relations = new if replace else {**st.session_state.relations, **new}


def coerce(value):
    if value is None:
        return None
    v = value.strip()
    if v == "":
        return None
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return v


def csv_to_rows(text):
    reader = csv.DictReader(io.StringIO(text))
    return [{k: coerce(v) for k, v in row.items() if k is not None} for row in reader]


def rows_to_csv(rows, cols):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def workspace_json():
    return json.dumps({n: r.rows for n, r in st.session_state.relations.items()},
                      indent=2, default=str, ensure_ascii=False)


def join_graph_dot(rels):
    names = list(rels)
    lines = ['graph G { rankdir=LR; node [shape=box, style="rounded"];']
    for n in names:
        lines.append(f'"{n}" [label="{n}\\n{len(rels[n].rows)} rows"];')
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = set(get_columns(rels[a])) & set(get_columns(rels[b]))
            if shared:
                lines.append(f'"{a}" -- "{b}" [label="{", ".join(sorted(shared))}"];')
    lines.append("}")
    return "\n".join(lines)


# =============================================================================
# Query Engine & AST Translators
# =============================================================================
def chain_nodes(node):
    """Unrolls both method chains A.f(x).g(y) and nested functional calls g(f(A))."""
    nodes = []
    curr = node
    # Method chain
    if isinstance(curr, ast.Call) and isinstance(curr.func, ast.Attribute):
        while isinstance(curr, ast.Call) and isinstance(curr.func, ast.Attribute):
            nodes.append(curr)
            curr = curr.func.value
        nodes.append(curr)
        return nodes[::-1]

    # Nested functional DSL call: PROJECT(..., SELECT(..., EMPLOYEE))
    def collect_nested(n):
        if isinstance(n, ast.Call):
            for arg in n.args:
                if isinstance(arg, ast.Call):
                    collect_nested(arg)
            nodes.append(n)

    collect_nested(node)
    return nodes if nodes else [node]


def step_label(node):
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            args = ", ".join(ast.unparse(a) for a in node.args)
            return f".{node.func.attr}({args})"[:90]
        if isinstance(node.func, ast.Name):
            args = ", ".join(ast.unparse(a) for a in node.args)
            return f"{node.func.id}({args})"[:90]
    return ast.unparse(node)


def to_algebra(node):
    """Translates Python method-chains or DSL AST nodes into textbook relational algebra notation."""
    try:
        if isinstance(node, ast.Call):
            # 1. Functional DSL Calls: SELECT("Dno = 5", EMPLOYEE)
            if isinstance(node.func, ast.Name):
                fn = node.func.id
                if fn in ("SELECT", "σ"):
                    cond = ast.literal_eval(node.args[0])
                    return f"σ[{cond}]({to_algebra(node.args[1])})"
                if fn in ("PROJECT", "π", "PI"):
                    cols = ", ".join(map(str, ast.literal_eval(node.args[0])))
                    return f"π[{cols}]({to_algebra(node.args[1])})"
                if fn in ("JOIN", "⋈", "THETA_JOIN"):
                    cond = ast.literal_eval(node.args[0])
                    return f"({to_algebra(node.args[1])} ⋈[{cond}] {to_algebra(node.args[2])})"
                if fn in ("NATURAL_JOIN",):
                    return f"({to_algebra(node.args[0])} ⨝ {to_algebra(node.args[1])})"
                if fn in ("UNION", "∪"):
                    return f"({to_algebra(node.args[0])} ∪ {to_algebra(node.args[1])})"
                if fn in ("INTERSECT", "∩"):
                    return f"({to_algebra(node.args[0])} ∩ {to_algebra(node.args[1])})"
                if fn in ("MINUS", "DIFFERENCE"):
                    return f"({to_algebra(node.args[0])} − {to_algebra(node.args[1])})"
                if fn in ("PRODUCT", "×", "CARTESIAN_PRODUCT"):
                    return f"({to_algebra(node.args[0])} × {to_algebra(node.args[1])})"
                if fn in ("AGGREGATE", "γ", "F", "ℱ"):
                    groups = ast.literal_eval(node.args[0])
                    aggs = ast.literal_eval(node.args[1])
                    agg_str = ", ".join(f"{f}({c})" for f, c in aggs)
                    return f"γ[{', '.join(groups)}; {agg_str}]({to_algebra(node.args[2])})"

            # 2. Method Chain: Employee.select(...).project(...)
            if isinstance(node.func, ast.Attribute):
                inner = to_algebra(node.func.value)
                op, args = node.func.attr, node.args
                if op == "project":
                    return f"π[{', '.join(map(str, ast.literal_eval(args[0])))}]({inner})"
                if op == "select":
                    if isinstance(args[0], ast.Lambda):
                        var = args[0].args.args[0].arg
                        cond = ast.unparse(args[0].body)
                        cond = re.sub(rf"\b{re.escape(var)}\[(['\"])(\w+)\1\]", r"\2", cond)
                        for old, new in ((" and ", " ∧ "), (" or ", " ∨ "), ("not ", "¬"),
                                         ("!=", "≠"), ("==", "="), (">=", "≥"), ("<=", "≤")):
                            cond = cond.replace(old, new)
                        return f"σ[{cond}]({inner})"
                    if isinstance(args[0], ast.Constant):
                        return f"σ[{args[0].value}]({inner})"
                if op == "natural_join":
                    return f"({inner} ⨝ {to_algebra(args[0])})"
                if op == "aggregate":
                    groups = ast.literal_eval(args[0])
                    aggs = ast.literal_eval(args[1])
                    agg = ", ".join(f"{f}({c})" for f, c in aggs)
                    return f"γ[{', '.join(groups)}; {agg}]({inner})"
                return f"{op}({inner})"
        return ast.unparse(node)
    except Exception:
        return ast.unparse(node)


def friendly_hint(exc, relations):
    all_cols = sorted({c for r in relations.values() for c in get_columns(r)})
    if isinstance(exc, KeyError) and exc.args:
        bad = str(exc.args[0])
        close = difflib.get_close_matches(bad, all_cols, n=3, cutoff=0.5)
        msg = f"Column `{bad}` was not found."
        if close:
            msg += " Did you mean " + ", ".join(f"`{c}`" for c in close) + "?"
        return msg + " Columns in workspace: " + ", ".join(all_cols)
    if isinstance(exc, NameError):
        m = re.search(r"'(\w+)'", str(exc))
        bad = m.group(1) if m else ""
        valid_identifiers = list(relations) + list(RA_DSL)
        close = difflib.get_close_matches(bad, valid_identifiers, n=3, cutoff=0.5)
        msg = f"`{bad}` is not defined."
        if close:
            msg += " Did you mean " + ", ".join(f"`{c}`" for c in close) + "?"
        return msg + " Available tables: " + ", ".join(relations)
    if isinstance(exc, AttributeError):
        ops = [n for n in dir(Relation) if not n.startswith("_")]
        return "Available operators: " + ", ".join(ops)
    if isinstance(exc, SyntaxError):
        return "Check brackets, quotes and commas. Nested relational queries must have matched parentheses."
    return None


def run_query(code, relations, trace=True):
    # Context injected with Safe Builtins, Relations, and the RA DSL wrappers
    ns = {"__builtins__": SAFE_BUILTINS, **relations, **RA_DSL}
    out = {"code": code, "ok": False, "result": None, "trace": [], "new": {},
           "algebra": None, "error": None, "tb": None, "hint": None, "ms": 0.0}
    t0 = time.perf_counter()
    try:
        tree = ast.parse(code.strip(), mode="exec")
        if not tree.body:
            raise ValueError("The query is empty.")
        last = tree.body[-1]
        final_node, result_name = None, None
        if isinstance(last, ast.Expr):
            final_node = tree.body.pop().value
        elif isinstance(last, ast.Assign) and len(last.targets) == 1 and isinstance(last.targets[0], ast.Name):
            result_name = last.targets[0].id
        else:
            raise ValueError("A script must end with an expression or a `Name = …` assignment.")

        if tree.body:
            exec(compile(tree, "<query>", "exec"), ns)

        if final_node is not None:
            steps = chain_nodes(final_node) if trace else [final_node]
            result = None
            for node in steps:
                result = eval(compile(ast.Expression(node), "<query>", "eval"), ns)
                if trace and len(steps) > 1:
                    out["trace"].append((step_label(node), result))
            out["algebra"] = to_algebra(final_node)
        else:
            result = ns[result_name]

        out["result"] = result
        out["new"] = {k: v for k, v in ns.items()
                      if k not in SAFE_BUILTINS and k not in RA_DSL and isinstance(v, Relation) and relations.get(k) is not v}
        out["ok"] = True
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        out["tb"] = traceback.format_exc()
        out["hint"] = friendly_hint(exc, relations)
    out["ms"] = (time.perf_counter() - t0) * 1000
    return out


def example_queries(rels):
    ex, names = [], list(rels)
    if not names:
        return ex
    t = names[0]
    cols = get_columns(rels[t])
    if cols:
        ex.append(("Formal PROJECT (π)", f"PROJECT({cols[:2]!r}, {t})"))
    num = numeric_cols(rels[t])
    if num:
        c = num[0]
        vals = sorted(r[c] for r in rels[t].rows if isinstance(r.get(c), (int, float)))
        med = vals[len(vals) // 2] if vals else 0
        ex.append(("Formal SELECT + PROJECT",
                   f"PROJECT({cols[:2]!r}, SELECT(\"{c} >= {med}\", {t}))"))
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = [c for c in get_columns(rels[a]) if c in get_columns(rels[b])]
            if shared:
                ex.append((f"Natural Join {a} ⨝ {b}", f"NATURAL_JOIN({a}, {b})"))
                ex.append((f"Theta Join {a} ⋈ {b}",
                           f"JOIN(\"{a}.{shared[0]} = {b}.{shared[0]}\", {a}, {b})"))
                n_a = [c for c in numeric_cols(rels[a]) if c not in shared]
                if n_a:
                    ex.append((f"Aggregate {a} (ℱ/γ)",
                               f"AGGREGATE([{shared[0]!r}], [('AVG', {n_a[0]!r})], {a})"))
                break
    ex.append(("Multi-statement pipeline",
               f"HighEarners = SELECT(\"Salary > 5000\", Employee)\nPROJECT(['Name', 'Salary'], HighEarners)"))
    return ex


def discover_operators():
    rows = []
    # Class methods
    for name, fn in inspect.getmembers(Relation, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue
        sig = str(inspect.signature(fn)).replace("(self, ", "(").replace("(self)", "()")
        doc = (inspect.getdoc(fn) or "").splitlines()
        rows.append({"Category": "Method", "Operator": name, "Signature": sig, "Description": doc[0] if doc else ""})
    # Lecture DSL functions
    dsl_docs = {
        "SELECT / σ": 'SELECT(condition_str, relation) -> Filter rows using human-readable conditions (e.g. "Dno = 5 AND Salary > 30000")[cite: 14, 15]',
        "PROJECT / π": 'PROJECT(attribute_list, relation) -> Retain specified columns, removing duplicates[cite: 17, 18]',
        "RENAME / ρ": 'RENAME(new_table_name, columns_map, relation) -> Rename relation or attributes[cite: 20]',
        "JOIN / ⋈": 'JOIN(condition_str, rel1, rel2) -> Theta join on arbitrary condition[cite: 31, 33]',
        "NATURAL_JOIN / ⨝": 'NATURAL_JOIN(rel1, rel2) -> Natural join on all identical column names[cite: 33, 34]',
        "UNION / ∪": 'UNION(rel1, rel2) -> Set union of two union-compatible relations[cite: 24]',
        "INTERSECT / ∩": 'INTERSECT(rel1, rel2) -> Set intersection of two relations[cite: 24]',
        "MINUS / DIFFERENCE": 'MINUS(rel1, rel2) -> Set difference (rel1 - rel2)[cite: 24]',
        "PRODUCT / ×": 'PRODUCT(rel1, rel2) -> Full Cartesian product[cite: 28]',
        "AGGREGATE / γ / ℱ": 'AGGREGATE(group_by_cols, [(func, col)], relation) -> Grouping & summary operations[cite: 46, 48]',
    }
    for op, desc in dsl_docs.items():
        rows.append({"Category": "Lecture DSL", "Operator": op, "Signature": "DSL Wrapper", "Description": desc})
    return rows


# =============================================================================
# Callbacks
# =============================================================================
def load_sample():
    ingest(SAMPLE_DATA, replace=True)
    st.session_state.file_sig = None


def reset_workspace():
    st.session_state.relations = {}
    st.session_state.last = None
    st.session_state.builder = {"base": None, "steps": []}
    st.session_state.file_sig = None


def load_query(code):
    st.session_state.query_input = code


def send_to_sandbox(code):
    st.session_state.query_input = code
    st.toast("Sent to the Sandbox tab ✔")


def save_result(name, rows):
    if not name.isidentifier():
        st.toast("Table names must be valid identifiers (letters, digits, _).")
        return
    st.session_state.relations[name] = Relation(name=name, rows=[dict(r) for r in rows])
    st.toast(f"Saved table `{name}`")


def try_ingest(loader, replace, ok_msg):
    try:
        ingest(loader(), replace=replace)
        st.success(ok_msg)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        st.error(f"Could not load data: {exc}")


# =============================================================================
# Result Rendering
# =============================================================================
def render_trace(trace):
    summary = [{"step": i, "operation": lbl,
                "rows": len(getattr(r, "rows", [])), "columns": len(get_columns(r)) if hasattr(r, "rows") else 0}
               for i, (lbl, r) in enumerate(trace)]
    show_table(summary, hide_index=True)
    for i, (lbl, r) in enumerate(trace):
        if hasattr(r, "rows"):
            with st.expander(f"Step {i}: {lbl}  →  {len(r.rows)} rows"):
                show_table(r.rows)


def render_outcome(o):
    if o is None:
        return
    if not o["ok"]:
        st.error(f"⚠️ {o['error']}")
        if o["hint"]:
            st.info("💡 " + o["hint"])
        if o["trace"]:
            st.markdown("**Steps that succeeded before the failure**")
            render_trace(o["trace"])
        with st.expander("Traceback"):
            st.code(o["tb"], language="bash")
        return

    res = o["result"]
    if not hasattr(res, "rows"):
        st.success("The query returned a value that is not a relation:")
        st.write(res)
        return

    cols = get_columns(res)
    m1, m2, m3 = st.columns(3)
    m1.metric("Rows", len(res.rows))
    m2.metric("Columns", len(cols))
    m3.metric("Execution Time", f"{o['ms']:.1f} ms")
    if o["algebra"]:
        st.markdown("**Formal Relational Algebra Notation**[cite: 9, 44]")
        st.code(o["algebra"], language="text")
    if o["new"]:
        st.caption("Tables created by this script: " + ", ".join(f"`{k}`" for k in o["new"]))

    t_table, t_chart, t_trace, t_export = st.tabs(["📋 Table", "📈 Chart", "🪜 Pipeline trace", "💾 Export / Save"])

    with t_table:
        show_table(res.rows)

    with t_chart:
        nums = numeric_cols(res)
        if not nums or not res.rows:
            st.info("Charts need at least one numeric column and one row.")
        else:
            c1, c2, c3 = st.columns([1, 2, 1])
            x = c1.selectbox("X axis", cols, key="chart_x")
            ys = c2.multiselect("Y axis", nums, default=nums[:1], key="chart_y")
            kind = c3.radio("Type", ["Bar", "Line", "Area", "Scatter"], horizontal=True, key="chart_kind")
            if ys:
                df = pd.DataFrame(res.rows)
                {"Bar": st.bar_chart, "Line": st.line_chart,
                 "Area": st.area_chart, "Scatter": st.scatter_chart}[kind](df, x=x, y=ys)

    with t_trace:
        if o["trace"]:
            render_trace(o["trace"])
        else:
            st.info("Chain two or more operations or nest DSL expressions to trace intermediate steps.")

    with t_export:
        d1, d2 = st.columns(2)
        d1.download_button("⬇ Download CSV", rows_to_csv(res.rows, cols),
                           file_name=f"{res.name}.csv", mime="text/csv")
        d2.download_button("⬇ Download JSON", json.dumps(res.rows, indent=2, default=str, ensure_ascii=False),
                           file_name=f"{res.name}.json", mime="application/json")
        new_name = st.text_input("Save result as a new table", value="Result", key="save_name")
        st.button("💾 Save to workspace", on_click=save_result, args=(new_name, res.rows))


# =============================================================================
# Sidebar
# =============================================================================
with st.sidebar:
    st.header("🗂 Workspace")
    rels = st.session_state.relations
    if rels:
        st.metric("Tables", len(rels))
        st.caption(" · ".join(f"`{n}` ({len(r.rows)})" for n, r in rels.items()))
        st.download_button("⬇ Export workspace (JSON)", workspace_json(),
                           file_name="workspace.json", mime="application/json")
    else:
        st.caption("Nothing loaded yet.")
    s1, s2 = st.columns(2)
    s1.button("✨ Sample", on_click=load_sample, help="Load sample company dataset")
    s2.button("🗑 Reset", on_click=reset_workspace)

    with st.expander("⭐ Saved queries", expanded=False):
        if not st.session_state.saved:
            st.caption("Use ⭐ Save in the Sandbox.")
        for i, q in enumerate(st.session_state.saved):
            c1, c2 = st.columns([4, 1])
            c1.button(q.replace("\n", " ")[:38] or "(empty)", key=f"sv_{i}", on_click=load_query, args=(q,))
            if c2.button("✕", key=f"sv_del_{i}"):
                st.session_state.saved.pop(i)
                st.rerun()

    with st.expander("🕘 History", expanded=True):
        if not st.session_state.history:
            st.caption("Executed queries show up here.")
        for i, h in enumerate(reversed(st.session_state.history[-8:])):
            icon = "✅" if h["ok"] else "❌"
            st.button(f"{icon} {h['query'].replace(chr(10), ' ')[:34]}", key=f"hi_{i}",
                      on_click=load_query, args=(h["query"],), help=f"{h['rows']} rows · {h['ms']:.1f} ms")


# =============================================================================
# Main Tabs
# =============================================================================
tab_data, tab_schema, tab_builder, tab_sandbox, tab_ref = st.tabs(
    ["📂 Load data", "📊 Schema", "🧱 Query builder", "⚡ Sandbox", "📖 Reference"])

# --- TAB 1: Load Data ---
with tab_data:
    st.markdown("### Import datasets")
    replace = st.toggle("Replace current workspace instead of merging", value=False)
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**JSON file**")
        up = st.file_uploader("Keys = tables, values = lists of rows", type=["json"], key="json_up")
        if up is not None:
            sig = ("json", up.name, up.size)
            if sig != st.session_state.file_sig:
                st.session_state.file_sig = sig
                try_ingest(lambda: json.loads(up.getvalue().decode("utf-8")), replace, f"Loaded {up.name}")

    with c2:
        st.markdown("**CSV files**")
        ups = st.file_uploader("Each file becomes a table", type=["csv"], accept_multiple_files=True, key="csv_up")
        if ups:
            sig = ("csv", tuple((f.name, f.size) for f in ups))
            if sig != st.session_state.file_sig:
                st.session_state.file_sig = sig
                try_ingest(lambda: {f.name.rsplit(".", 1)[0]: csv_to_rows(f.getvalue().decode("utf-8-sig"))
                                    for f in ups}, replace, f"Loaded {len(ups)} CSV file(s)")

    with c3:
        st.markdown("**Paste JSON**")
        manual = st.text_area("Paste JSON", height=150, label_visibility="collapsed",
                              placeholder='{"Employee": [{"ID": 1, "Name": "Ali"}]}', key="paste_json")
        if st.button("Load pasted JSON"):
            if manual.strip():
                try_ingest(lambda: json.loads(manual), replace, "Pasted JSON loaded")

    st.divider()
    st.button("✨ Load sample company dataset", on_click=load_sample, key="sample_main")

# --- TAB 2: Schema ---
with tab_schema:
    rels = st.session_state.relations
    if not rels:
        st.warning("No data loaded yet. Use the first tab or load the ✨ Sample.")
    else:
        if len(rels) > 1:
            st.markdown("#### Join graph")
            st.caption("Tables that share column names can be combined via `NATURAL_JOIN`.")
            st.graphviz_chart(join_graph_dot(rels))
        st.markdown("#### Tables")
        for name, rel in list(rels.items()):
            with st.expander(f"📦 {name}  ({len(rel.rows)} rows × {len(get_columns(rel))} cols)"):
                p1, p2 = st.columns([3, 2])
                with p1:
                    show_table(rel.rows)
                with p2:
                    st.caption("Column profile")
                    show_table(column_profile(rel), hide_index=True)
                if st.toggle("✏️ Edit data", key=f"edit_toggle_{name}"):
                    edited = st.data_editor(pd.DataFrame(rel.rows), num_rows="dynamic", key=f"editor_{name}")
                    if st.button("💾 Apply edits", key=f"apply_{name}"):
                        clean = edited.astype(object).where(edited.notna(), None).to_dict("records")
                        st.session_state.relations[name] = Relation(name=name, rows=clean)
                        st.rerun()
                if st.button("Delete table", key=f"del_{name}"):
                    st.session_state.relations.pop(name)
                    st.rerun()

# --- TAB 3: Query Builder ---
with tab_builder:
    rels = st.session_state.relations
    if not rels:
        st.warning("Load data first.")
    else:
        b = st.session_state.builder
        names = list(rels)
        if b["base"] not in rels:
            b["base"], b["steps"] = names[0], []
        base = st.selectbox("Start from", names, index=names.index(b["base"]))
        if base != b["base"]:
            b["base"], b["steps"] = base, []

        code = b["base"]
        for s in b["steps"]:
            # Wrap incrementally with DSL syntax
            code = s.replace("{TARGET}", code)

        preview = run_query(code, rels, trace=False)
        cols_now = get_columns(preview["result"]) if preview["ok"] and hasattr(preview["result"], "rows") else []

        st.markdown("#### Add a step")
        op = st.selectbox("Operation", ["σ Select (filter rows)", "π Project (keep columns)",
                                        "⨝ Natural join", "γ Aggregate (group & summarise)"])
        fragment = None
        if op.startswith("σ"):
            a, o_, v = st.columns([2, 1, 2])
            col = a.selectbox("Column", cols_now, key="b_sel_col")
            cmp_ = o_.selectbox("Operator", ["=", "!=", ">", ">=", "<", "<="], key="b_sel_op")
            val = v.text_input("Value", key="b_sel_val")
            if col and val != "":
                parsed = coerce(val)
                cond_val = f"'{parsed}'" if isinstance(parsed, str) else str(parsed)
                fragment = f"SELECT(\"{col} {cmp_} {cond_val}\", {{TARGET}})"
        elif op.startswith("π"):
            keep = st.multiselect("Columns to keep", cols_now, key="b_proj")
            if keep:
                fragment = f"PROJECT({keep!r}, {{TARGET}})"
        elif op.startswith("⨝"):
            other = st.selectbox("Join with", names, key="b_join")
            fragment = f"NATURAL_JOIN({{TARGET}}, {other})"
        else:
            g, f_, c_ = st.columns(3)
            groups = g.multiselect("Group by", cols_now, key="b_agg_g")
            funcs = f_.multiselect("Functions", ["AVG", "SUM", "COUNT", "MIN", "MAX"], default=["AVG"], key="b_agg_f")
            acol = c_.selectbox("Column", cols_now, key="b_agg_c")
            if funcs and acol:
                fragment = f"AGGREGATE({groups!r}, {[(f, acol) for f in funcs]!r}, {{TARGET}})"

        bc1, bc2, bc3, _ = st.columns([1, 1, 1, 3])
        if bc1.button("➕ Add step", disabled=fragment is None):
            b["steps"].append(fragment)
            st.rerun()
        if bc2.button("↩ Undo", disabled=not b["steps"]):
            b["steps"].pop()
            st.rerun()
        if bc3.button("Clear", disabled=not b["steps"], key="b_clear"):
            b["steps"] = []
            st.rerun()

        st.markdown("#### Generated query")
        st.code(code, language="python")
        if preview["ok"] and hasattr(preview["result"], "rows"):
            st.caption(f"Live preview: {len(preview['result'].rows)} rows × {len(cols_now)} columns")
            show_table(preview["result"].rows)
        elif not preview["ok"]:
            st.error(preview["error"])
        st.button("⚡ Send to Sandbox", on_click=send_to_sandbox, args=(code,))

# --- TAB 4: Sandbox ---
with tab_sandbox:
    rels = st.session_state.relations
    st.markdown("### Execute Relational Algebra (Lecture Syntax)")
    left, right = st.columns([2, 1])

    with right:
        st.markdown("#### 📖 Lecture Cheat Sheet")
        st.markdown("**Unary Operations**[cite: 9]")
        st.code('PROJECT(["Name", "Salary"], Employee)  # π\nSELECT("Salary > 5000 AND DeptID = 10", Employee)  # σ\nRENAME("Staff", {"Name": "FullName"}, Employee)  # ρ')
        st.markdown("**Joins & Products**[cite: 28, 31, 34]")
        st.code('NATURAL_JOIN(Employee, Department)  # ⨝\nJOIN("Employee.DeptID = Department.DeptID", Employee, Department)  # ⋈\nPRODUCT(Employee, Project)  # ×')
        st.markdown("**Aggregation & Sets**[cite: 24, 48]")
        st.code('AGGREGATE(["DeptID"], [("AVG", "Salary")], Employee)  # γ\nUNION(R1, R2)  # ∪\nMINUS(R1, R2)  # -')
        st.caption("You can use either English words (`SELECT`, `PROJECT`) or Greek symbols (`σ`, `π`, `⨝`, `γ`)[cite: 9, 44].")

        st.divider()
        st.markdown("#### 💡 Example Queries")
        examples = example_queries(rels)
        if examples:
            labels = [e[0] for e in examples]
            pick = st.selectbox("Pick example", labels, key="example_pick")
            st.code(dict(examples)[pick], language="python")
            st.button("Insert into editor", on_click=load_query, args=(dict(examples)[pick],))

    with left:
        query = st.text_area(
            "Enter Relational Algebra expression / script:",
            height=180,
            key="query_input",
            placeholder='PROJECT(["Name", "Salary"], SELECT("Salary > 5000", Employee))'
        )
        o1, o2 = st.columns(2)
        trace_on = o1.toggle("Trace each step in pipeline", value=True)
        keep_vars = o2.toggle("Persist assigned intermediate tables", value=True)
        b1, b2, b3, _ = st.columns([1.2, 1, 1, 3])
        run = b1.button("▶ Execute Query", type="primary")
        if b2.button("⭐ Save"):
            if query.strip() and query not in st.session_state.saved:
                st.session_state.saved.append(query)
                st.rerun()
        if b3.button("Clear", key="sb_clear"):
            st.session_state.query_input = ""
            st.session_state.last = None
            st.rerun()

        if run:
            if not rels:
                st.error("Please load data first!")
            elif not query.strip():
                st.warning("Please enter a query.")
            else:
                outcome = run_query(query, rels, trace=trace_on)
                st.session_state.last = outcome
                n = len(outcome["result"].rows) if outcome["ok"] and hasattr(outcome["result"], "rows") else 0
                st.session_state.history.append({"query": query, "ok": outcome["ok"], "rows": n, "ms": outcome["ms"]})
                st.session_state.history = st.session_state.history[-30:]
                if outcome["ok"] and keep_vars and outcome["new"]:
                    st.session_state.relations.update(outcome["new"])

    st.divider()
    render_outcome(st.session_state.last)

# --- TAB 5: Reference ---
with tab_ref:
    st.markdown("### Supported Relational Algebra Operations")
    show_table(discover_operators(), hide_index=True)
    st.markdown("### Formal Lecture Mapping")
    show_table([
        {"Symbol": "σ", "Operation": "SELECT", "Example Condition": '"Salary >= 5000 AND DeptID = 10"', "Slides Ref": "Slide 8-8 / 8-9"},
        {"Symbol": "π", "Operation": "PROJECT", "Example Condition": '["Name", "Salary"]', "Slides Ref": "Slide 8-11 / 8-12"},
        {"Symbol": "ρ", "Operation": "RENAME", "Example Condition": '"NewName", {"OldCol": "NewCol"}', "Slides Ref": "Slide 8-14"},
        {"Symbol": "⋈", "Operation": "THETA JOIN", "Example Condition": '"Emp.DeptID = Dept.DeptID"', "Slides Ref": "Slide 8-25"},
        {"Symbol": "⨝", "Operation": "NATURAL JOIN", "Example Condition": "Automatic matching on shared columns", "Slides Ref": "Slide 8-28"},
        {"Symbol": "γ / ℱ", "Operation": "AGGREGATE", "Example Condition": '["DeptID"], [("AVG", "Salary")]', "Slides Ref": "Slide 8-41"},
        {"Symbol": "∪ / ∩ / −", "Operation": "SET OPS", "Example Condition": "UNION, INTERSECT, MINUS", "Slides Ref": "Slide 8-18"},
    ], hide_index=True)