"""Contract check: deploy-qa.yml must only pass declared Bicep params and read declared outputs."""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def compiled(template: str) -> dict:
    result = subprocess.run(
        ["az", "bicep", "build", "--file", str(ROOT / template), "--stdout"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def main() -> int:
    workflow = (ROOT / ".github/workflows/deploy-qa.yml").read_text()
    failures: list[str] = []

    checks = [
        ("infra/qa-deployment.bicep", "--template-file infra/qa-deployment.bicep"),
        ("infra/ui.bicep", "--template-file infra/ui.bicep"),
        ("infra/ui-stack.bicep", "--template-file infra/ui-stack.bicep"),
    ]

    for template, marker in checks:
        tpl = compiled(template)
        declared = set(tpl.get("parameters", {}))
        block = workflow.split(marker)[1].split("--query")[0]
        passed = set(re.findall(r"([A-Za-z][A-Za-z0-9]*)=", block))
        # Drop shell-expansion artifacts, keep real parameter names.
        passed = {p for p in passed if p in declared or not p.isupper()}
        unknown = passed - declared
        print(f"{template}: passes {sorted(passed)}")
        if unknown:
            failures.append(f"{template}: undeclared parameters {sorted(unknown)}")

    qa_outputs = set(compiled("infra/qa-deployment.bicep").get("outputs", {}))
    ui_outputs = set(compiled("infra/ui.bicep").get("outputs", {}))
    used = set(re.findall(r"properties\.outputs\.([A-Za-z_]+)\.value", workflow))
    used |= set(re.findall(r"\.([A-Za-z_]+)\.value'", workflow))
    missing = used - qa_outputs - ui_outputs
    print(f"outputs referenced: {sorted(used)}")
    if missing:
        failures.append(f"outputs not declared by any template: {sorted(missing)}")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1

    print("PASS: workflow and Bicep templates agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
