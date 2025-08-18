from __future__ import annotations

import ast
import io
import json
import sys
import time
import traceback
from typing import Any, Dict

import pandas as pd  # noqa: F401  (exposed through allow-list)
import numpy as np  # noqa: F401
from sklearn import model_selection, preprocessing, metrics, linear_model, ensemble  # noqa: F401
import xgboost as xgb  # noqa: F401
import optuna  # noqa: F401
import joblib  # noqa: F401
import matplotlib
import builtins as _b

matplotlib.use("Agg")


SAFE_BUILTINS: Dict[str, Any] = {
    "print": _b.print,
    "len": _b.len,
    "range": _b.range,
    "min": _b.min,
    "max": _b.max,
    "sum": _b.sum,
    "round": _b.round,
    "bool": _b.bool,
    "any": _b.any,
    "all": _b.all,
    "zip": _b.zip,
    "sorted": _b.sorted,
    "isinstance": _b.isinstance,
    "type": _b.type,
    "pow": _b.pow,
    "map": _b.map,
    "filter": _b.filter,
    "repr": _b.repr,
    "enumerate": _b.enumerate,
    "list": _b.list,
    "dict": _b.dict,
    "set": _b.set,
    "tuple": _b.tuple,
    "abs": _b.abs,
    "int": _b.int,
    "float": _b.float,
    "str": _b.str,
    "__import__": _b.__import__,  # allow library imports; user code blocked via AST
    "open": _b.open,  # allow libraries to write files; user code blocked via AST
}

ALLOWED: Dict[str, Any] = {
    "pd": pd,
    "np": np,
    "model_selection": model_selection,
    "preprocessing": preprocessing,
    "metrics": metrics,
    "linear_model": linear_model,
    "ensemble": ensemble,
    "xgboost": xgb,
    "optuna": optuna,
    "joblib": joblib,
    "__builtins__": SAFE_BUILTINS,  # expose only safe subset
}

BANNED_IMPORTS = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "requests",
    "urllib",
    "pathlib",
    "importlib",
}

BANNED_NAMES = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "dir",
    "input",
    "help",
    "exit",
    "quit",
}


def safe_compile(code: str):
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in BANNED_NAMES:
            raise ValueError(f"Name banned: {node.id}")
        if isinstance(node, ast.Import):
            for n in node.names:
                root = n.name.split(".")[0]
                if root in BANNED_IMPORTS:
                    raise ValueError(f"Import banned: {root}")
        if isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in BANNED_IMPORTS:
                raise ValueError(f"ImportFrom banned: {root}")
        if isinstance(node, ast.Attribute):
            if node.attr in {"system", "popen", "execv", "spawn"}:
                raise ValueError(f"Attribute banned: {node.attr}")
            if node.attr.startswith("__") and node.attr.endswith("__"):
                raise ValueError("Dunder attribute access banned")
    return compile(tree, "<cell>", "exec")


def run_step(step_json: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Any]:
    code = step_json["python"]
    compiled = safe_compile(code)
    out, err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    artifacts: Dict[str, Any] = {}
    start = time.time()
    status = "ok"
    try:
        sys.stdout, sys.stderr = out, err
        exec(compiled, ALLOWED, {"inputs": inputs, "artifacts": artifacts})
    except Exception:
        status = "error"
        traceback.print_exc(file=err)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return {
        "status": status,
        "stdout": out.getvalue(),
        "stderr": err.getvalue(),
        # NOTE: Prefer file paths over large in-memory objects. Small JSON-like
        # dicts are acceptable for MVP and will be serialized by the orchestrator.
        "artifacts": artifacts,
        "duration_sec": round(time.time() - start, 3),
    }


if __name__ == "__main__":
    # Simple CLI to run a step JSON from stdin for development
    payload = json.load(sys.stdin)
    result = run_step(payload["step"], payload.get("inputs", {}))
    json.dump(result, sys.stdout)
