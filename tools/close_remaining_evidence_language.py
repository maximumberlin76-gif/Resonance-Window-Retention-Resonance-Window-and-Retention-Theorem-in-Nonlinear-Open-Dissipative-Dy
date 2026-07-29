#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path.cwd()
ZIP_TIME = (2026, 7, 29, 0, 0, 0)
V35 = "resonance_system_v35_HYBRID_MULTI_GAS_REGIME_MATRIX_TRUE.zip"
FINAL = "FINAL_THEOREM_PACKAGE_REBUILT_TRUE.zip"
SOURCE_HASHES = {
    "README.md": "9314d41266d4a7ac09b927cedde8a0aadd76362aa788dd3adaa03ccd0cc9fc9b",
    "EVIDENCE_STATUS.md": "a83f626babf02c2a58ef18f0e5b9bd7108c3c394fd92e0369e4a6497fe54d65c",
    "experimental_historical_archive/README.md": "5ac068943a7452848623c9307eb97af0f73cc00e4c0cd0ab337658e2dfb34628",
    V35: "0823f017e2cab73d2ea236674ec3cefee2d5ab364c02f6cee595d4bf2f95ab2d",
    FINAL: "521aa26fb9601e4f4ce2003158f099a1844db379d52eed2c55b95f05aa3e57aa",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, value: object) -> None:
    write(path, json.dumps(value, indent=2, ensure_ascii=False))


def block(*items: str) -> str:
    return "\n".join(items)


def replace_exact(text: str, old: str, new: str, count: int, label: str) -> str:
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{label}: expected {count}, found {actual}")
    return text.replace(old, new)


def replace_section(text: str, start: str, end: str, replacement: str, label: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        raise SystemExit(f"{label}: section markers are not unique")
    left = text.index(start)
    right = text.index(end, left)
    return text[:left] + replacement.rstrip() + "\n\n" + text[right:]


def verify_source() -> None:
    for relative, expected in SOURCE_HASHES.items():
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"Missing source file: {relative}")
        actual = sha256(path)
        if actual != expected:
            raise SystemExit(
                f"Source hash mismatch: {relative}\nexpected {expected}\nactual   {actual}"
            )


def safe_extract(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source, "r") as archive:
        for member in archive.infolist():
            relative = Path(member.filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise SystemExit(f"Unsafe ZIP member: {source.name}/{member.filename}")
        archive.extractall(target)


def pack(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = ((0o755 if path.suffix == ".py" else 0o644) & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())


def write_manifest(root: Path, relative_manifest: str) -> None:
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative != relative_manifest:
            rows.append(f"{sha256(path)}  {relative}")
    write(root / relative_manifest, "\n".join(rows))


def verify_manifest(root: Path, relative_manifest: str) -> None:
    for row in read(root / relative_manifest).splitlines():
        if not row.strip():
            continue
        expected, relative = row.split("  ", 1)
        if sha256(root / relative) != expected:
            raise SystemExit(f"Manifest mismatch: {root.name}/{relative}")


def verify_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        damaged = archive.testzip()
        if damaged is not None:
            raise SystemExit(f"ZIP integrity failure: {path.name}/{damaged}")


def run_v35(root: Path) -> None:
    engine = subprocess.run(
        [sys.executable, "scripts/engine_v35_hybrid_multi_gas_regime_matrix.py", "--outdir", "results"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    write(root / "logs/engine_stdout.txt", engine.stdout)
    write(root / "logs/engine_stderr.txt", engine.stderr)
    if engine.returncode != 0:
        raise SystemExit(f"v35 engine failed:\n{engine.stderr}")

    smoke = subprocess.run(
        [sys.executable, "tests/smoke_test.py"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    write(root / "logs/smoke_stdout.txt", smoke.stdout)
    write(root / "logs/smoke_stderr.txt", smoke.stderr)
    if smoke.returncode != 0:
        raise SystemExit(f"v35 smoke test failed:\n{smoke.stderr}")

    validation_path = root / "validation/validation_summary.json"
    validation = json.loads(read(validation_path))
    validation["engine_returncode"] = engine.returncode
    validation["smoke_returncode"] = smoke.returncode
    validation["status"] = "terminology_closed_and_numerically_rechecked"
    validation["critical_status"] = {
        relative: {"exists": (root / relative).is_file(), "size": (root / relative).stat().st_size}
        for relative in [
            "scripts/engine_v35_hybrid_multi_gas_regime_matrix.py",
            "results/hybrid_multi_gas_regime_matrix_summary.json",
            "results/hybrid_multi_gas_regime_matrix_summary.md",
            "docs/README.md",
            "model/equations_v35.md",
            "journal/session_journal_v35.md",
        ]
    }
    write_json(validation_path, validation)
    write_manifest(root, "checksums/sha256_manifest.txt")
    verify_manifest(root, "checksums/sha256_manifest.txt")


def correct_root_readme(text: str) -> str:
    replacements = [
        ("- computational validation frameworks,", "- computational evidence and evaluation frameworks,", 1, "framework list"),
        ("proof-chain and operational validation architecture", "proof-chain and operational evidence architecture", 1, "architecture description"),
        ("- validation transparency,", "- evidence-status transparency,", 3, "transparency terminology"),
        (
            "The plasma models contained in this repository are operational validation frameworks for a broader class of nonlinear dissipative open dynamic systems in which structure formation depends on:",
            "The plasma models contained in this repository are computational evaluation frameworks for a broader class of nonlinear dissipative open dynamic systems in which structure formation depends on:",
            1,
            "plasma framework classification",
        ),
        (
            "Current repository layers include preserved experimental structures and validation archives from:",
            "Current repository layers include preserved computational structures and evidence archives from:",
            1,
            "historical archive classification",
        ),
        (
            "Historical validation chains and reconstruction archives are progressively integrated into the repository as part of the long-term operational research structure.",
            "Historical computational chains and reconstruction archives are progressively integrated into the repository as part of the long-term operational research structure.",
            1,
            "historical chain classification",
        ),
        ("- computational validation layers,", "- computational evidence layers,", 1, "status layer classification"),
        ("- additional nonlinear validation environments,", "- additional nonlinear evaluation environments,", 1, "future environment classification"),
        ("- validation environments spanning v1 → v35,", "- computational evidence archives spanning v1 → v35,", 1, "repository status classification"),
        ("structured proof-chain and operational validation archive", "structured proof-chain and operational evidence archive", 1, "repository archive classification"),
        ("- a computational validation structure,", "- a computational evidence structure,", 1, "computational structure classification"),
    ]
    for old, new, count, label in replacements:
        text = replace_exact(text, old, new, count, label)

    framework = block(
        "# Computational Evidence and Evaluation Framework",
        "",
        "The repository contains formal criteria, historical computational archives, deterministic design-space prioritization, engineering scoring, and Monte Carlo configuration-screening packages for retained operational stability in nonlinear dissipative open dynamic systems.",
        "",
        "These layers support reconstruction, candidate comparison, parameter-space exploration, and evidence classification. They do not by themselves constitute independent time-resolved dynamic or experimental validation.",
        "",
        "The computational chain addresses:",
        "",
        "- resonance-window entry criteria,",
        "",
        "- coherent accumulation proxies and invariants,",
        "",
        "- transient destabilization and chaotic-transition scenarios,",
        "",
        "- retained-domain criteria,",
        "",
        "- adaptive stabilization and recovery scenarios,",
        "",
        "- post-forcing persistence requirements,",
        "",
        "- and explicit boundaries between formal claims, historical simulations, scoring models, and screening results.",
        "",
        "## Evidence Classification",
        "",
        "The repository separates theorem-level definitions and acceptance criteria, historical executable reconstruction packages, deterministic design-space prioritization, deterministic engineering scoring, Monte Carlo configuration screening, and successor requirements for independent dynamic evidence.",
        "",
        "Transient amplification, temporary synchronization, or externally forced coherence-support responses are not treated as proof of retained synthesis.",
        "",
        "## Plasma Evaluation Layers",
        "",
        "The plasma-oriented packages examine configured hybrid acoustic/electromagnetic regimes, multi-gas candidate sequences, perturbation scenarios, retention criteria, coherence-reconstruction pathways, and nonlinear stabilization assumptions.",
        "",
        "The active v35-series packages are classified by their actual computational operations. Their outputs are candidate rankings and screening results, not measurements of physical channel superiority.",
        "",
        "## Chaotic Transition Analysis",
        "",
        "Historical and formal layers examine chaotic-transition corridors, coherence fragmentation, nonlinear destabilization, metastable states, adaptive relock behavior, and resonance re-entry conditions.",
        "",
        "These layers preserve model evolution and candidate mechanisms for later controlled testing.",
        "",
        "## Recovery and Adaptive Stabilization",
        "",
        "The framework defines recovery survivability, post-instability persistence, adaptive coherence reconstruction, and retained-domain restoration as operational research targets.",
        "",
        "## Retention-Oriented Acceptance Criteria",
        "",
        "A retained candidate requires accumulated positive structural work, positive structural balance over completed periods, retained-domain membership, bounded perturbation response, and persistence after reduction of external driving.",
        "",
        "The central formal condition is:",
        "",
        "- F_ext(t) → 0",
        "",
        "while:",
        "",
        "- x(t) ∈ Ω_ret",
        "",
        "continues to hold over the defined retention interval.",
        "",
        "## Computational Objectives",
        "",
        "The repository preserves executable reconstruction, parameter-space exploration, candidate ranking, theorem continuity, and explicit evidence boundaries for resonance-assisted organization and retention dynamics.",
    )
    text = replace_section(text, "# Experimental Validation Framework", "# Repository Structure", framework, "evidence framework section")

    layer = block(
        "## Computational Evidence Layer",
        "",
        "The computational evidence layer contains:",
        "",
        "- historical plasma simulations,",
        "",
        "- active design-space prioritization and engineering-scoring packages,",
        "",
        "- Monte Carlo configuration screening,",
        "",
        "- perturbation and recovery scenarios,",
        "",
        "- reproducibility records,",
        "",
        "- and evidence-status documentation.",
        "",
        "Repository sections may include:",
        "",
        "- /experiments_index/",
        "",
        "- /experimental_parameters/",
    )
    text = replace_section(text, "## Experimental Validation Layer", "## Adaptive Coherence Layer", layer, "computational evidence layer")

    forbidden = [
        "# Experimental Validation Framework",
        "## Experimental Validation Layer",
        "computational and experimental validation layers",
        "operational validation architecture",
        "plasma-oriented validation environments",
        "operational validation architectures",
        "validation environments spanning v1 → v35",
        "structured proof-chain and operational validation archive",
        "computational validation structure",
    ]
    for marker in forbidden:
        if marker in text:
            raise SystemExit(f"Root README stale marker remains: {marker}")
    return text
  def historical_readme() -> str:
    return block(
        "# Historical Computational Proof-Chain",
        "",
        "This directory preserves the executable and documentary evolution of the resonance-window and retention framework for nonlinear dissipative open dynamic systems.",
        "",
        "The archive preserves package sequence, parameter variation, computational model evolution, reconstruction pathways, and evidence-status boundaries.",
        "",
        "# Preserved Computational Structure",
        "",
        "The archive includes resonance-window simulations, hybrid retention configurations, acoustic-entry hypotheses, electromagnetic-retention hypotheses, multi-gas plasma models, retained-domain criteria, stress-test packages, and long-duration retention analyses.",
        "",
        "# Historical Hybrid Hypothesis",
        "",
        "The archived packages encode and explore a proposed separation between entry and retention mechanisms.",
        "",
        "The historical channel assignments were acoustic entry, electromagnetic retention support, and a hybrid candidate architecture.",
        "",
        "These assignments are hypotheses embedded in historical configurations. They are not independently established by the active v35-series scoring and screening packages.",
        "",
        "# Computational Progression",
        "",
        "The preserved chain includes initial resonance-entry simulations, hybrid stabilization configurations, invariant calculations, retained-domain criteria, deep-hybrid screening, and extended retention scenarios.",
        "",
        "# Evidence Criteria",
        "",
        "The formal acceptance structure requires accumulated positive structural work, persistence over completed periods, retained-domain stability, bounded perturbation response, reproducibility across declared parameter variations, and post-forcing operational persistence.",
        "",
        "Temporary synchronization, phase alignment, or short-lived coherence-support response is insufficient.",
        "",
        "# Historical Chain",
        "",
        "The archive preserves the computational sequence v1 → v35, including simulation evolution, parameter-space expansion, hybrid-stabilization refinement, retained-domain formalization, and theorem consolidation.",
        "",
        "# Repository Structure",
        "",
        "This directory contains experiment packages, simulation archives, parameter studies, retention analyses, theorem-development chains, and reproducibility records.",
        "",
        "# Historical Evidence Boundary",
        "",
        "The ZIP archives in this directory remain byte-for-byte unchanged.",
        "",
        "The cited v30, v31, and v33 generations do not include matched `F_ext = 0` controls in the published package series; many cited coupling regimes are strongly supercritical; legacy `C` fields are model-specific `R`-dependent proxies; and the cyclic-frequency / angular-frequency convention requires correction in a successor engine.",
        "",
        "These archives document model evolution and executable history. They do not constitute current independent dynamic evidence for external-forcing retention.",
    )


def correct_status(text: str) -> str:
    if "## Public-Language Closure" in text:
        raise SystemExit("EVIDENCE_STATUS.md closure section already exists")
    return text.rstrip() + "\n\n" + block(
        "## Public-Language Closure",
        "",
        "The remaining public-facing evidence labels were synchronized after the first corrective pass.",
        "",
        "Closed items:",
        "",
        "- root repository sections now distinguish computational evidence, evaluation, scoring, screening, and independent dynamic evidence,",
        "",
        "- the historical archive README now identifies preserved packages as computational history rather than current proof,",
        "",
        "- v35 uses `legacy_reference_ratio` for the historical input coefficient without changing numerical rankings,",
        "",
        "- the final theorem package identifies separate versioned packages as computational evidence packages,",
        "",
        "- and obsolete one-time correction workflow files are removed after the closure run.",
    ) + "\n"


def patch_v35(root: Path) -> None:
    summary_path = root / "results/hybrid_multi_gas_regime_matrix_summary.json"
    baseline = json.loads(read(summary_path))

    config_path = root / "configs/config.json"
    config = json.loads(read(config_path))
    former_key = "known" + "_valid_ratio"
    for gas_name, gas in config["gases"].items():
        if former_key not in gas:
            raise SystemExit(f"v35 source key missing for gas: {gas_name}")
        config["gases"][gas_name] = {
            ("legacy_reference_ratio" if key == former_key else key): value
            for key, value in gas.items()
        }
    write_json(config_path, config)

    engine_path = root / "scripts/engine_v35_hybrid_multi_gas_regime_matrix.py"
    engine = replace_exact(
        read(engine_path),
        former_key,
        "legacy_reference_ratio",
        2,
        "v35 engine field rename",
    )
    write(engine_path, engine)

    equations_path = root / "model/equations_v35.md"
    write(
        equations_path,
        read(equations_path).rstrip()
        + "\n\n"
        + block(
            "Configured reference term:",
            "",
            "legacy_reference_ratio = historical package ratio used only as an input coefficient in the prioritization score",
            "",
            "The field name does not assert current physical validity.",
        ),
    )

    smoke_path = root / "tests/smoke_test.py"
    smoke = replace_exact(
        read(smoke_path),
        'assert all("expected_mode" not in row for row in s["hybrid_sequence_rank"])',
        block(
            'assert all("expected_mode" not in row for row in s["hybrid_sequence_rank"])',
            'cfg = json.load(open("configs/config.json", "r", encoding="utf-8"))',
            'former_key = "known" + "_valid_ratio"',
            'assert former_key not in json.dumps(s, ensure_ascii=False)',
            'assert former_key not in json.dumps(cfg, ensure_ascii=False)',
            'assert all("legacy_reference_ratio" in gas for gas in cfg["gases"].values())',
        ),
        1,
        "v35 smoke terminology checks",
    )
    write(smoke_path, smoke)

    journal_path = root / "journal/session_journal_v35.md"
    write(
        journal_path,
        read(journal_path).rstrip()
        + "\n\n"
        + block(
            "## Public-Language Closure — 2026-07-29",
            "",
            "The former validity-labelled input field was renamed to `legacy_reference_ratio`.",
            "",
            "The numerical values and prioritization equations were not changed.",
        ),
    )

    run_v35(root)
    updated = json.loads(read(summary_path))

    if former_key in json.dumps(updated, ensure_ascii=False):
        raise SystemExit("v35 stale field remains in regenerated summary")

    if "legacy_reference_ratio" not in json.dumps(updated, ensure_ascii=False):
        raise SystemExit("v35 renamed field missing from regenerated summary")

    if baseline["main_conclusion"] != updated["main_conclusion"]:
        raise SystemExit("v35 main conclusion changed unexpectedly")

    if baseline["recommended_start"] != updated["recommended_start"]:
        raise SystemExit("v35 recommended start changed unexpectedly")

    if baseline["normalized_corridor"] != updated["normalized_corridor"]:
        raise SystemExit("v35 normalized corridor changed unexpectedly")

    if [
        (item["gas"], item["score"])
        for item in baseline["gas_rank"]
    ] != [
        (item["gas"], item["score"])
        for item in updated["gas_rank"]
    ]:
        raise SystemExit("v35 gas ranking or scores changed unexpectedly")

    baseline_sequences = [
        (
            item["sequence"],
            item["score"],
            item["screening_status"],
        )
        for item in baseline["hybrid_sequence_rank"]
    ]

    updated_sequences = [
        (
            item["sequence"],
            item["score"],
            item["screening_status"],
        )
        for item in updated["hybrid_sequence_rank"]
    ]

    if baseline_sequences != updated_sequences:
        raise SystemExit("v35 sequence ranking or scores changed unexpectedly")


def patch_final(root: Path) -> None:
    index_path = root / "PACKAGE_INDEX.json"
    index = json.loads(read(index_path))

    old = "index for experimental validation packages"

    if index.get("intended_use", []).count(old) != 1:
        raise SystemExit("Final package intended-use marker mismatch")

    index["intended_use"] = [
        (
            "index for computational evidence packages"
            if item == old
            else item
        )
        for item in index["intended_use"]
    ]

    index.setdefault("evidence_status", {})[
        "boundary"
    ] = "configured_computational_ranking_not_time_resolved_dynamic_validation"

    write_json(index_path, index)

    replacements = [
        (
            root / "zenodo/zenodo_description.md",
            "The experimental validation layer is provided through separate versioned packages in the repository.",
            "The computational evidence layer is provided through separate versioned packages in the repository; their classifications and inference boundaries are stated in the repository evidence-status document.",
            "Zenodo evidence classification",
        ),
        (
            root / "experiments_index/github_upload_order.md",
            "## Commit 4 — Deep hybrid validation",
            "## Commit 4 — Deep hybrid configuration screening",
            "upload-order classification",
        ),
        (
            root / "resonance_process/resonance_properties.md",
            "## Property 4 — Retention-Based Validation",
            "## Property 4 — Retention-Based Acceptance",
            "resonance-property heading",
        ),
    ]

    for path, old_text, new_text, label in replacements:
        write(
            path,
            replace_exact(
                read(path),
                old_text,
                new_text,
                1,
                label,
            ),
        )

    reproducibility_path = root / "experiments_index/reproducibility_matrix.md"
    write(
        reproducibility_path,
        read(reproducibility_path).rstrip()
        + "\n\n"
        + block(
            "## Directory-Name Boundary",
            "",
            "The `validation/` directory name denotes execution checks, package-integrity records, and declared acceptance checks. It does not by itself assert independent physical validation.",
        ),
    )

    report_path = root / "validation/package_integrity_report.json"
    report = json.loads(read(report_path))
    report["status"] = "public_evidence_language_closed_and_rechecked"
    report["file_count"] = len(
        [
            path
            for path in root.rglob("*")
            if path.is_file()
        ]
    )
    write_json(report_path, report)

    write_manifest(
        root,
        "checksums/SHA256SUMS.txt",
    )

    verify_manifest(
        root,
        "checksums/SHA256SUMS.txt",
    )

    stale = [
        "index for experimental validation packages",
        "The experimental validation layer is provided",
        "Deep hybrid validation",
        "Retention-Based Validation",
    ]

    for path in root.rglob("*"):
        if (
            not path.is_file()
            or path.suffix.lower()
            in {".png", ".jpg", ".jpeg"}
        ):
            continue

        try:
            content = read(path)
        except UnicodeDecodeError:
            continue

        for marker in stale:
            if marker in content:
                raise SystemExit(
                    f"Final package stale marker remains: {path}: {marker}"
                )


def main() -> None:
    verify_source()

    archives = sorted(
        (
            ROOT
            / "experimental_historical_archive"
        ).glob("*.zip")
    )

    if not archives:
        raise SystemExit(
            "No historical ZIP archives found"
        )

    archive_hashes = {
        path: sha256(path)
        for path in archives
    }

    corrected_readme = correct_root_readme(
        read(ROOT / "README.md")
    )

    corrected_historical = historical_readme()

    corrected_status = correct_status(
        read(ROOT / "EVIDENCE_STATUS.md")
    )

    with tempfile.TemporaryDirectory(
        prefix="rwr-language-closure-"
    ) as temporary:
        temp = Path(temporary)

        v35_root = temp / "v35"
        final_root = temp / "final"

        safe_extract(
            ROOT / V35,
            v35_root,
        )

        safe_extract(
            ROOT / FINAL,
            final_root,
        )

        patch_v35(v35_root)
        patch_final(final_root)

        v35_zip = temp / V35
        final_zip = temp / FINAL

        pack(
            v35_root,
            v35_zip,
        )

        pack(
            final_root,
            final_zip,
        )

        verify_zip(v35_zip)
        verify_zip(final_zip)

        staged = {
            temp / "README.md": (
                ROOT / "README.md",
                corrected_readme,
            ),
            temp / "historical_README.md": (
                ROOT
                / "experimental_historical_archive"
                / "README.md",
                corrected_historical,
            ),
            temp / "EVIDENCE_STATUS.md": (
                ROOT / "EVIDENCE_STATUS.md",
                corrected_status,
            ),
        }

        for source, (_, content) in staged.items():
            write(source, content)

        for source, (target, _) in staged.items():
            os.replace(
                source,
                target,
            )

        os.replace(
            v35_zip,
            ROOT / V35,
        )

        os.replace(
            final_zip,
            ROOT / FINAL,
        )

    for path, expected in archive_hashes.items():
        if sha256(path) != expected:
            raise SystemExit(
                "Historical archive changed unexpectedly: "
                f"{path}"
            )

    verify_zip(
        ROOT / V35
    )

    verify_zip(
        ROOT / FINAL
    )

    public_text = (
        read(ROOT / "README.md")
        + "\n"
        + read(
            ROOT
            / "experimental_historical_archive"
            / "README.md"
        )
    )

    forbidden = [
        "# Experimental Validation Framework",
        "## Experimental Validation Layer",
        "operational validation architecture",
        "plasma-oriented validation environments",
        "hybrid validation layers",
        "theorem validation chains",
        "invariant validation",
        "retained-domain validation",
        "known" + "_valid_ratio",
    ]

    for marker in forbidden:
        if marker in public_text:
            raise SystemExit(
                f"Public stale marker remains: {marker}"
            )

    print(
        "Remaining evidence-language closure completed and verified."
    )


if __name__ == "__main__":
    main()
