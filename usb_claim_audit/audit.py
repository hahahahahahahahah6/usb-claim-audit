"""Offline document and AST analysis; audited code is never executed."""
import ast
import fnmatch
import re
from pathlib import Path
from .phrases import USB, NOUSB


def pattern(phrases):
    return re.compile(r"\b(?:" + "|".join(re.escape(p) for p in sorted(phrases, key=len, reverse=True)) + r")\b")


def claims(text):
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not line[match.end():].strip():
                fence = None
            lines.append("")
        elif match:
            fence = match[1]
            lines.append("")
        else:
            lines.append(line)
    positive = negative = False
    for paragraph in re.split(r"\n\s*\n", "\n".join(lines)):
        normalized = re.sub(r"\s+", " ", paragraph.lower().replace("n't", " not").replace("-", " "))
        negative |= bool(pattern(NOUSB).search(normalized))
        normalized = pattern(NOUSB).sub(" ", normalized)
        positive |= bool(pattern(USB).search(normalized))
    return positive, negative


def evidence(source):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return False
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name == "usb" or item.name.startswith("usb."):
                    aliases[item.asname or item.name.split(".")[0]] = item.name if item.asname else "usb"
        elif isinstance(node, ast.ImportFrom) and node.module and (node.module == "usb" or node.module.startswith("usb.")):
            for item in node.names:
                aliases[item.asname or item.name] = node.module + "." + item.name
    def resolve(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, "")
        if isinstance(node, ast.Attribute):
            base = resolve(node.value)
            return base + "." + node.attr if base else ""
        return ""
    # Discovery itself is evidence, including every bound or chained route.
    return any(isinstance(n, ast.Call) and resolve(n.func) == "usb.core.find" for n in ast.walk(tree))


def audit(root, ignore=(), fail_on="HIGH"):
    root = Path(root)
    if not root.is_dir():
        raise ValueError("root must be a readable directory")
    if root.stat().st_mode & 0o444 == 0 or root.stat().st_mode & 0o111 == 0:
        raise ValueError("root must be a readable directory")
    positive = negative = prod = test = False
    scanned = 0
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_symlink() or any((root / Path(*rel.parts[:i])).is_symlink() for i in range(1, len(rel.parts))):
            continue
        if any(fnmatch.fnmatch(rel.as_posix(), glob) for glob in ignore):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() == ".md" and (rel.as_posix() == "README.md" or "docs" in rel.parts[:-1]):
            a, b = claims(path.read_text(encoding="utf-8"))
            positive |= a
            negative |= b
            scanned += 1
        if path.suffix == ".py":
            if any(p in {"fixtures", "docs", "examples"} for p in rel.parts[:-1]):
                continue
            is_test = "tests" in rel.parts[:-1] or path.name.startswith("test_") or path.name.endswith("_test.py")
            found = evidence(path.read_text(encoding="utf-8"))
            test |= found and is_test
            prod |= found and not is_test
            scanned += 1
    findings = []
    if positive and not prod:
        findings.append(dict(rule="documented-usb-claim-false", severity="MEDIUM" if test else "HIGH", message="Documented wired device capability lacks production evidence."))
    if negative and prod:
        findings.append(dict(rule="documented-no-usb-claim-false", severity="HIGH", message="Documented absence conflicts with production discovery evidence."))
    failed = any(f["severity"] == "HIGH" or fail_on == "MEDIUM" for f in findings)
    return dict(verdict="FAIL" if failed else "PASS", findings=findings, scanned=scanned)
