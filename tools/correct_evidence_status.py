#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path.cwd()
ZIP_TIME = (2026, 7, 29, 0, 0, 0)

PACKAGES = {
    "v35": (
        "resonance_system_v35_HYBRID_MULTI_GAS_REGIME_MATRIX_TRUE.zip",
        "9d40616122a1f2c7c37f2430eab3ef7641f1ac62aa457ed49e0931084b9a1f0b",
    ),
    "v351": (
        "resonance_system_v35_1_AR_HE_HYBRID_ACOUSTIC_EM_RETENTION_TRUE.zip",
        "8d243c99caeadfd8721ccf6f84496a114b2d94c634d30f22a62b7701a66facce",
    ),
    "v352": (
        "resonance_system_v35_2_AR_HE_H_DEEP_HYBRID_TESTS_TRUE.zip",
        "f9e73277a380ca8cbe16883fac5384a0eb8c76e760a731eca4a95c0a62e79a2c",
    ),
    "v353": (
        "resonance_system_v35_3_HYBRID_RETENTION_THEOREM_PACKAGE_TRUE.zip",
        "d30e802f5b9db8a1816df79ff4fc750108760d12835563b5877eeb70cc1f9295",
    ),
    "final": (
        "FINAL_THEOREM_PACKAGE_REBUILT_TRUE.zip",
        "0cd53bf53764243ea81d2c4eeafc86efdc92a7bcf08d62a3b43ee76710bbdf74",
    ),
}


def lines(*items: str) -> str:
    return "\n".join(items)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        text.rstrip() + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_json(path: Path, value: object) -> None:
    write(
        path,
        json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
        ),
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def replace_once(
    text: str,
    old: str,
    new: str,
    label: str,
) -> str:
    count = text.count(old)

    if count != 1:
        raise SystemExit(
            f"{label}: expected 1 occurrence, "
            f"found {count}"
        )

    return text.replace(old, new)


def replace_section(
    text: str,
    start: str,
    end: str,
    replacement: str,
    label: str,
) -> str:
    if (
        text.count(start) != 1
        or text.count(end) != 1
    ):
        raise SystemExit(
            f"{label}: section markers "
            "are not unique"
        )

    left = text.index(start)
    right = text.index(end, left)

    return (
        text[:left]
        + replacement.rstrip()
        + "\n"
        + text[right:]
    )


def verify_source() -> None:
    if (
        ROOT
        / "EVIDENCE_STATUS.md"
    ).exists():
        raise SystemExit(
            "EVIDENCE_STATUS.md already exists"
        )

    for name, expected in PACKAGES.values():
        path = ROOT / name

        if not path.is_file():
            raise SystemExit(
                f"Missing package: {name}"
            )

        actual = sha256(path)

        if actual != expected:
            raise SystemExit(
                f"Package hash mismatch: {name}\n"
                f"expected {expected}\n"
                f"actual   {actual}"
            )

    markers = {
        "README.md": [
            "# Why the Scaling Is Cubic",
            "t_delay ~ v^(−1/3)",
            (
                "hybrid acoustic/"
                "electromagnetic plasma "
                "retention experiments"
            ),
        ],
        (
            "experimental_historical_archive/"
            "README.md"
        ): [
            "# Experimental Proof-Chain",
            "# Hybrid Validation Logic",
        ],
        "theorems/README.md": [
            (
                "# Hybrid Retention Theorem"
                "\n\n"
                "## Statement"
            ),
            (
                "F_acoustic → initiates entry "
                "into the resonance window"
            ),
            "F_EM → stabilizes Ω_ret",
        ],
    }

    for relative, required in markers.items():
        path = ROOT / relative

        if not path.is_file():
            raise SystemExit(
                f"Missing document: {relative}"
            )

        text = read(path)

        for marker in required:
            if marker not in text:
                raise SystemExit(
                    "Missing marker in "
                    f"{relative}: {marker}"
                )


def safe_extract(
    source: Path,
    target: Path,
) -> None:
    target.mkdir(
        parents=True,
        exist_ok=True,
    )

    with zipfile.ZipFile(
        source,
        "r",
    ) as archive:
        for member in archive.infolist():
            relative = Path(
                member.filename
            )

            if (
                relative.is_absolute()
                or ".." in relative.parts
            ):
                raise SystemExit(
                    "Unsafe ZIP member: "
                    f"{source.name}/"
                    f"{member.filename}"
                )

        archive.extractall(target)


def pack(
    source: Path,
    target: Path,
) -> None:
    temporary = target.with_suffix(
        target.suffix + ".tmp"
    )

    if temporary.exists():
        temporary.unlink()

    with zipfile.ZipFile(
        temporary,
        "w",
        zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        files = sorted(
            path
            for path in source.rglob("*")
            if path.is_file()
        )

        for path in files:
            relative = path.relative_to(
                source
            ).as_posix()

            info = zipfile.ZipInfo(
                relative,
                ZIP_TIME,
            )

            info.compress_type = (
                zipfile.ZIP_DEFLATED
            )

            info.create_system = 3

            mode = (
                0o755
                if path.suffix == ".py"
                else 0o644
            )

            info.external_attr = (
                (mode & 0xFFFF) << 16
            )

            archive.writestr(
                info,
                path.read_bytes(),
            )

    os.replace(
        temporary,
        target,
    )


def write_manifest(
    root: Path,
    relative_manifest: str,
) -> None:
    rows = []

    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
    )

    for path in files:
        relative = path.relative_to(
            root
        ).as_posix()

        if relative != relative_manifest:
            rows.append(
                f"{sha256(path)}  {relative}"
            )

    write(
        root / relative_manifest,
        "\n".join(rows),
    )


def verify_manifest(
    root: Path,
    relative_manifest: str,
) -> None:
    manifest = root / relative_manifest

    if not manifest.is_file():
        raise SystemExit(
            "Missing manifest: "
            f"{root.name}/"
            f"{relative_manifest}"
        )

    for row in read(
        manifest
    ).splitlines():
        if not row.strip():
            continue

        expected, relative = row.split(
            "  ",
            1,
        )

        if (
            sha256(root / relative)
            != expected
        ):
            raise SystemExit(
                "Manifest mismatch: "
                f"{root.name}/"
                f"{relative}"
            )


def run_package(
    root: Path,
    engine: str,
) -> None:
    run = subprocess.run(
        [
            sys.executable,
            engine,
            "--outdir",
            "results",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    write(
        root / "logs/engine_stdout.txt",
        run.stdout,
    )

    write(
        root / "logs/engine_stderr.txt",
        run.stderr,
    )

    if run.returncode != 0:
        raise SystemExit(
            f"Engine failed in {root.name}: "
            f"{run.stderr}"
        )

    smoke = subprocess.run(
        [
            sys.executable,
            "tests/smoke_test.py",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    write(
        root / "logs/smoke_stdout.txt",
        smoke.stdout,
    )

    write(
        root / "logs/smoke_stderr.txt",
        smoke.stderr,
    )

    if smoke.returncode != 0:
        raise SystemExit(
            f"Smoke test failed in "
            f"{root.name}: "
            f"{smoke.stderr}"
        )

    write_manifest(
        root,
        "checksums/sha256_manifest.txt",
    )

    verify_manifest(
        root,
        "checksums/sha256_manifest.txt",
    )


def correct_root() -> None:
    path = ROOT / "README.md"
    text = read(path)

    intro = (
        "This repository presents a "
        "theoretical and computational "
        "framework for resonance-driven "
        "self-organization, coherent "
        "accumulation, retained operational "
        "regimes, and dynamic synthesis in "
        "nonlinear dissipative open dynamic "
        "systems."
    )

    boundary = lines(
        "## Computational Evidence Boundary",
        "",
        (
            "The theorem layer and the "
            "computational package layer have "
            "different evidential functions."
        ),
        "",
        (
            "The active v35, v35.1, and v35.2 "
            "packages are design-space "
            "prioritization, engineering "
            "scoring, and Monte Carlo "
            "configuration-screening models."
        ),
        "",
        (
            "They reproduce configured "
            "calculations but do not "
            "independently integrate a plasma "
            "or oscillator state through time. "
            "They therefore do not constitute "
            "time-resolved dynamic validation "
            "of acoustic, electromagnetic, or "
            "hybrid channel superiority."
        ),
        "",
        (
            "The v35.3 package preserves the "
            "Hybrid Retention Theorem with the "
            "corrected v35.2 screening package. "
            "Historical ZIP archives remain "
            "unchanged."
        ),
        "",
        (
            "See "
            "[EVIDENCE_STATUS.md]"
            "(EVIDENCE_STATUS.md)."
        ),
    )

    text = replace_once(
        text,
        intro,
        intro + "\n\n" + boundary,
        "README boundary",
    )

    text = replace_once(
        text,
        (
            "- and hybrid acoustic/"
            "electromagnetic plasma retention "
            "experiments."
        ),
        (
            "- and hybrid acoustic/"
            "electromagnetic design-scoring "
            "and configuration-screening "
            "packages."
        ),
        "README package classification",
    )

    text = replace_once(
        text,
        (
            "The hybrid plasma model therefore "
            "functions as an experimental "
            "validation architecture for "
            "broader resonance-retention "
            "dynamics in nonlinear dissipative "
            "open dynamic systems."
        ),
        (
            "The hybrid plasma model therefore "
            "functions as an engineering "
            "hypothesis and candidate control "
            "architecture. The active "
            "v35-series packages rank "
            "configured candidates but do not "
            "independently validate the "
            "physical channel roles."
        ),
        "README hybrid claim",
    )

    scaling = lines(
        "# Cubic Critical Form and Scaling",
        "",
        (
            "Near the critical regime, "
            "the reduced form is:"
        ),
        "",
        "  * dC/dt = vtC − C³",
        "",
        "Use the rescaling:",
        "",
        "  * C = v^(1/4)y",
        "  * t = v^(−1/2)τ",
        "",
        (
            "The derivative, drift, and cubic "
            "terms then carry the same exponent:"
        ),
        "",
        "  * dC/dt ~ v^(3/4)",
        "  * vtC ~ v^(3/4)",
        "  * C³ ~ v^(3/4)",
        "",
        "Therefore:",
        "",
        "  * C ~ v^(1/4)",
        "  * t_delay ~ v^(−1/2)",
        "",
        (
            "The exponent follows from the "
            "simultaneous balance of the time "
            "derivative, the drift term, and "
            "the cubic saturation term. It "
            "does not follow from the cubic "
            "term alone."
        ),
        "",
    )

    text = replace_section(
        text,
        "# Why the Scaling Is Cubic",
        "- Ω(t)",
        scaling,
        "README scaling",
    )

    write(
        path,
        text,
    )

    historical = (
        ROOT
        / "experimental_historical_archive"
        / "README.md"
    )

    text = read(historical)

    text = replace_once(
        text,
        "# Experimental Proof-Chain",
        (
            "# Historical Computational "
            "Proof-Chain"
        ),
        "historical title",
    )

    old = lines(
        "# Hybrid Validation Logic",
        "",
        (
            "The experimental framework "
            "validates the separation between:"
        ),
        "",
        "entry mechanisms",
        "",
        "and",
        "",
        "retention mechanisms.",
        "",
        "The simulations demonstrate that:",
        "",
        (
            "- acoustic forcing accelerates "
            "resonance-window entry"
        ),
        "",
        (
            "- electromagnetic stabilization "
            "suppresses dispersion"
        ),
        "",
        (
            "- hybrid driving improves retained "
            "organization over time"
        ),
    )

    new = lines(
        "# Historical Hybrid Hypothesis",
        "",
        (
            "The archived packages encode and "
            "explore a proposed separation "
            "between entry and retention "
            "mechanisms."
        ),
        "",
        (
            "The historical channel assignments "
            "were acoustic entry, "
            "electromagnetic retention support, "
            "and a hybrid candidate architecture."
        ),
        "",
        (
            "These assignments are hypotheses "
            "embedded in the historical "
            "configurations. They are not "
            "independently established by the "
            "active v35-series scoring and "
            "screening packages."
        ),
    )

    text = replace_once(
        text,
        old,
        new,
        "historical hybrid section",
    )

    text += "\n\n" + lines(
        "# Historical Evidence Boundary",
        "",
        (
            "The ZIP archives in this directory "
            "remain byte-for-byte unchanged."
        ),
        "",
        (
            "The cited v30, v31, and v33 "
            "generations do not include matched "
            "`F_ext = 0` controls in the "
            "published package series; many "
            "cited coupling regimes are strongly "
            "supercritical; legacy `C` fields "
            "are model-specific `R`-dependent "
            "proxies; and the cyclic-frequency / "
            "angular-frequency convention "
            "requires correction in a successor "
            "engine."
        ),
        "",
        (
            "These archives document model "
            "evolution and executable history. "
            "They are not current independent "
            "validation evidence for "
            "external-forcing retention."
        ),
    )

    write(
        historical,
        text,
    )

    theorem = (
        ROOT
        / "theorems"
        / "README.md"
    )

    text = read(theorem)

    text = replace_once(
        text,
        (
            "# Hybrid Retention Theorem"
            "\n\n"
            "## Statement"
        ),
        lines(
            "# Hybrid Retention Theorem",
            "## Evidence Boundary",
            "",
            (
                "The theorem defines a candidate "
                "channel-separation architecture. "
                "The active v35.1 scoring package "
                "and v35.2 Monte Carlo screening "
                "package evaluate configured "
                "assumptions; they do not provide "
                "independent time-resolved "
                "dynamic validation of acoustic "
                "entry, electromagnetic "
                "retention, or hybrid superiority."
            ),
            "",
            "## Statement",
        ),
        "theorem boundary",
    )

    text = replace_once(
        text,
        (
            "F_acoustic → initiates entry into "
            "the resonance window → accelerates "
            "Θ_N accumulation"
        ),
        (
            "F_acoustic → candidate role: "
            "resonance-window entry and "
            "Θ_N accumulation"
        ),
        "theorem acoustic role",
    )

    text = replace_once(
        text,
        (
            "F_EM → stabilizes Ω_ret → "
            "suppresses phase dispersion → "
            "maintains retained organization"
        ),
        (
            "F_EM → candidate role: Ω_ret "
            "stabilization, phase-dispersion "
            "suppression, and retained "
            "organization"
        ),
        "theorem EM role",
    )

    write(
        theorem,
        text,
    )

    write(
        ROOT / "EVIDENCE_STATUS.md",
        lines(
            "# Computational Evidence Status",
            "",
            (
                "## Active Package "
                "Classification"
            ),
            "",
            (
                "| Package | Classification | "
                "Evidential function |"
            ),
            "|---|---|---|",
            (
                "| v35 | deterministic "
                "design-space prioritization "
                "matrix | ranks configured gas "
                "and sequence candidates |"
            ),
            (
                "| v35.1 | deterministic "
                "engineering design scoring | "
                "ranks configured channels, "
                "sequences, and a candidate "
                "protocol |"
            ),
            (
                "| v35.2 | Monte Carlo "
                "configuration screening | "
                "propagates configured "
                "coefficients and seeded "
                "perturbations through algebraic "
                "screening rules |"
            ),
            (
                "| v35.3 | theorem package with "
                "embedded corrected v35.2 "
                "screening evidence | preserves "
                "the theorem and its "
                "computational boundary |"
            ),
            (
                "| FINAL_THEOREM_PACKAGE_"
                "REBUILT_TRUE | publication core "
                "with corrected evidence "
                "classification | separates "
                "formal results from screening "
                "evidence |"
            ),
            "",
            "## Corrected v35.2 Ranking",
            "",
            "    em_only",
            "    → hybrid_em_retention",
            "    → hybrid_balanced",
            "    → hybrid_soft",
            "    → acoustic_only",
            "",
            (
                "This ranking is internal to the "
                "configured screening equations. "
                "It is not a measurement of "
                "physical channel superiority."
            ),
            "",
            (
                "## Critical Scaling "
                "Synchronization"
            ),
            "",
            "    C ~ v^(1/4)",
            "    t_delay ~ v^(−1/2)",
            "",
            (
                "The exponent is determined by "
                "the simultaneous balance of the "
                "derivative, drift, and cubic "
                "terms."
            ),
            "",
            (
                "## Successor Dynamic Evidence "
                "Requirements"
            ),
            "",
            (
                "- explicit time integration "
                "of state variables"
            ),
            (
                "- matched `F_ext = 0` controls "
                "for every parameter point "
                "and seed"
            ),
            (
                "- coupling regimes near the "
                "applicable critical threshold"
            ),
            (
                "- one frequency convention "
                "throughout equations, code, "
                "and reports"
            ),
            (
                "- separate diagnostics for "
                "phase order, general coherence, "
                "and endogenous contribution"
            ),
            (
                "- post-drive comparison against "
                "control over a defined retention "
                "interval"
            ),
        ),
    )


def patch_config(
    root: Path,
    values: dict[str, str],
) -> None:
    path = root / "configs/config.json"
    config = json.loads(read(path))
    config.update(values)
    write_json(path, config)


def append_journal(
    path: Path,
    heading: str,
    paragraphs: list[str],
) -> None:
    text = (
        read(path).rstrip()
        + "\n\n"
        + heading
    )

    for paragraph in paragraphs:
        text += "\n\n" + paragraph

    write(
        path,
        text,
    )


def patch_v35(root: Path) -> None:
    patch_config(
        root,
        {
            (
                "model_class"
            ): (
                "deterministic_design_space_"
                "prioritization_matrix"
            ),
            (
                "evidence_scope"
            ): (
                "configured_candidate_ranking_"
                "not_dynamic_validation"
            ),
        },
    )

    write(
        root / "docs/README.md",
        lines(
            (
                "# v35 — Hybrid Multi-Gas "
                "Design-Space Prioritization"
            ),
            "",
            (
                "Classification: deterministic "
                "design-space prioritization "
                "matrix."
            ),
            "",
            (
                "This package ranks configured "
                "gas and sequence candidates. "
                "It does not integrate plasma "
                "dynamics through time and does "
                "not constitute dynamic "
                "validation."
            ),
        ),
    )

    write(
        root / "model/equations_v35.md",
        lines(
            (
                "# v35 Configured "
                "Prioritization Equations"
            ),
            "",
            "Ω(t) → Ω(t, μ_env, χ_mix)",
            "",
            (
                "screening_status = "
                "candidate_for_dynamic_testing"
            ),
            "",
            (
                "The status marks a configured "
                "candidate only."
            ),
        ),
    )

    path = (
        root
        / (
            "scripts/"
            "engine_v35_hybrid_multi_gas_"
            "regime_matrix.py"
        )
    )

    text = read(path)

    replacements = [
        (
            (
                '"expected_mode": '
                '"hybrid_window_candidate" '
                'if sc > 0.35 else '
                '"requires_strict_mu_env_'
                'calibration"'
            ),
            (
                '"screening_status": '
                '"candidate_for_dynamic_testing" '
                'if sc > 0.35 else '
                '"requires_additional_'
                'configuration_review"'
            ),
            "v35 status",
        ),
        (
            (
                '"system_class": '
                'cfg["system_class"],'
            ),
            (
                '"system_class": '
                'cfg["system_class"],\n'
                '        "model_class": '
                'cfg["model_class"],\n'
                '        "evidence_scope": '
                'cfg["evidence_scope"],'
            ),
            "v35 metadata",
        ),
        (
            (
                '"main_conclusion": '
                '"hybrid_regime_should_use_'
                'inertial_buffer_plus_fast_'
                'probe_plus_molecular_'
                'calibration",'
            ),
            (
                '"main_conclusion": '
                '"configured_design_space_'
                'priority_is_" + '
                '"_then_".join('
                'seqs[0]["sequence"]),'
            ),
            "v35 conclusion",
        ),
        (
            (
                '"reason": "highest score under '
                'retention/response/dissipation/'
                'chemistry balance"'
            ),
            (
                '"reason": "highest configured '
                'score; requires independent '
                'dynamic testing"'
            ),
            "v35 reason",
        ),
        (
            (
                '"theorem_note": "For hybrid '
                'gas mixtures Ω(t) must be '
                'extended to '
                'Ω(t, μ_env, χ_mix), where '
                'μ_env captures medium '
                'parameters and χ_mix captures '
                'mixture composition."'
            ),
            (
                '"theorem_note": "The matrix '
                'prioritizes configured '
                'candidates and does not '
                'validate a physical resonance '
                'window."'
            ),
            "v35 note",
        ),
        (
            "mode={s['expected_mode']}",
            "status={s['screening_status']}",
            "v35 markdown",
        ),
    ]

    for old, new, label in replacements:
        text = replace_once(
            text,
            old,
            new,
            label,
        )

    write(
        path,
        text,
    )

    smoke = (
        root
        / "tests/smoke_test.py"
    )

    text = read(smoke)

    text = replace_once(
        text,
        (
            'assert "hybrid_sequence_rank" '
            "in s"
        ),
        lines(
            (
                'assert "hybrid_sequence_rank" '
                "in s"
            ),
            (
                'assert s["model_class"] == '
                '"deterministic_design_space_'
                'prioritization_matrix"'
            ),
            (
                'assert all("expected_mode" '
                "not in row for row in "
                's["hybrid_sequence_rank"])'
            ),
        ),
        "v35 smoke",
    )

    write(
        smoke,
        text,
    )

    append_journal(
        (
            root
            / (
                "journal/"
                "session_journal_v35.md"
            )
        ),
        (
            "## Evidence Classification "
            "Correction — 2026-07-29"
        ),
        [
            (
                "The package is classified as "
                "a deterministic design-space "
                "prioritization matrix."
            ),
        ],
    )

    run_package(
        root,
        (
            "scripts/"
            "engine_v35_hybrid_multi_gas_"
            "regime_matrix.py"
        ),
    )


def patch_v351(root: Path) -> None:
    patch_config(
        root,
        {
            (
                "model_class"
            ): (
                "deterministic_engineering_"
                "design_scoring"
            ),
            (
                "evidence_scope"
            ): (
                "configured_channel_and_"
                "sequence_ranking_not_"
                "dynamic_validation"
            ),
        },
    )

    write(
        root / "docs/README.md",
        lines(
            (
                "# v35.1 — Ar-He-H Acoustic + "
                "Electromagnetic Engineering "
                "Scoring"
            ),
            "",
            (
                "Classification: deterministic "
                "engineering design scoring."
            ),
            "",
            (
                "The package scores configured "
                "gas and channel coefficients. "
                "It does not integrate a plasma "
                "state through time."
            ),
        ),
    )

    write(
        root / "model/equations_v35_1.md",
        lines(
            (
                "# v35.1 Configured "
                "Engineering Scoring"
            ),
            "",
            (
                "F_total(t) = "
                "F_acoustic(t) + F_EM(t)"
            ),
            "",
            (
                "The package does not compute a "
                "time-resolved Θ_N trajectory "
                "or post-drive dynamics."
            ),
        ),
    )

    path = (
        root
        / (
            "scripts/"
            "engine_v35_1_ar_he_h_"
            "acoustic_em_retention.py"
        )
    )

    text = read(path)

    text = replace_once(
        text,
        (
            '"system_class": '
            'cfg["system_class"],'
        ),
        (
            '"system_class": '
            'cfg["system_class"],\n'
            '        "model_class": '
            'cfg["model_class"],\n'
            '        "evidence_scope": '
            'cfg["evidence_scope"],'
        ),
        "v351 metadata",
    )

    text = replace_once(
        text,
        (
            '"main_conclusion": '
            '"best_engineering_path_is_argon_'
            'buffer_with_acoustic_entry_and_'
            'em_retention_for_helium_hydrogen_'
            'transfer",'
        ),
        (
            '"main_conclusion": '
            '"configured_scoring_ranks_" + '
            'seq_results[0]["best_channel"] + '
            '"_for_" + "_then_".join('
            'seq_results[0]["sequence"]),'
        ),
        "v351 conclusion",
    )

    text = replace_once(
        text,
        (
            '"theorem_note": "Hybrid control '
            'separates entry channel from '
            'retention channel: acoustic drive '
            'is economical for Θ_N initiation, '
            'electromagnetic drive is superior '
            'for Ω_ret stabilization."'
        ),
        (
            '"theorem_note": "The channel-role '
            'separation is a configured '
            'engineering hypothesis. This '
            'package scores it and does not '
            'dynamically validate it."'
        ),
        "v351 note",
    )

    write(
        path,
        text,
    )

    smoke = (
        root
        / "tests/smoke_test.py"
    )

    text = replace_once(
        read(smoke),
        (
            'assert "operational_protocol" '
            "in s"
        ),
        lines(
            (
                'assert "operational_protocol" '
                "in s"
            ),
            (
                'assert s["model_class"] == '
                '"deterministic_engineering_'
                'design_scoring"'
            ),
        ),
        "v351 smoke",
    )

    write(
        smoke,
        text,
    )

    append_journal(
        (
            root
            / (
                "journal/"
                "session_journal_v35_1.md"
            )
        ),
        (
            "## Evidence Classification "
            "Correction — 2026-07-29"
        ),
        [
            (
                "The package is classified as "
                "deterministic engineering "
                "design scoring."
            ),
        ],
    )

    run_package(
        root,
        (
            "scripts/"
            "engine_v35_1_ar_he_h_"
            "acoustic_em_retention.py"
        ),
    )


def patch_v352(root: Path) -> None:
    patch_config(
        root,
        {
            (
                "model"
            ): (
                "Ar-He-H Monte Carlo "
                "configuration screening matrix"
            ),
            (
                "model_class"
            ): (
                "monte_carlo_configuration_"
                "screening"
            ),
            (
                "evidence_scope"
            ): (
                "algebraic_candidate_screening_"
                "not_time_resolved_dynamic_"
                "validation"
            ),
        },
    )

    write(
        root / "docs/README.md",
        lines(
            (
                "# v35.2 — Ar-He-H Monte Carlo "
                "Configuration Screening"
            ),
            "",
            (
                "Classification: Monte Carlo "
                "configuration screening model."
            ),
            "",
            (
                "The package propagates "
                "configured coefficients through "
                "algebraic screening equations "
                "with seeded perturbations. It "
                "does not contain time-resolved "
                "plasma dynamics or a matched "
                "no-drive control."
            ),
        ),
    )

    write(
        root / "model/equations_v35_2.md",
        lines(
            (
                "# v35.2 Algebraic Screening "
                "Equations"
            ),
            "",
            (
                "screening_candidate = "
                "Θ_N_proxy and balance_proxy and "
                "retention_tail_proxy and "
                "stable_periods_proxy and "
                "collapse_risk_proxy"
            ),
            "",
            (
                "A screening candidate requires "
                "independent dynamic testing."
            ),
        ),
    )

    path = (
        root
        / (
            "scripts/"
            "engine_v35_2_ar_he_h_"
            "deep_hybrid_tests.py"
        )
    )

    text = read(path)

    if (
        "valid_hybrid_resonance_window"
        not in text
    ):
        raise SystemExit(
            "v352 legacy outcome marker missing"
        )

    text = text.replace(
        "valid_hybrid_resonance_window",
        "screening_candidate",
    )

    text = text.replace(
        "valid_count",
        "candidate_count",
    )

    text = text.replace(
        "valid_ratio",
        "candidate_ratio",
    )

    replacements = [
        (
            (
                '"model": cfg["model"],'
            ),
            (
                '"model": cfg["model"],\n'
                '        "model_class": '
                'cfg["model_class"],\n'
                '        "evidence_scope": '
                'cfg["evidence_scope"],'
            ),
            "v352 metadata",
        ),
        (
            (
                '"best_scenarios": '
                "best_scenarios,"
            ),
            (
                '"best_scenarios": '
                "best_scenarios,\n"
                '        "configured_channel_'
                'ranking": [name for name, _ '
                "in best_channels],"
            ),
            "v352 ranking",
        ),
        (
            (
                '"main_conclusion": '
                '"hybrid_em_retention_and_'
                'hybrid_balanced_are_the_best_'
                'candidates_for_deep_Ar_He_H_'
                'testing",'
            ),
            (
                '"main_conclusion": '
                '"configured_screening_ranking_'
                'is_" + "_then_".join('
                "name for name, _ "
                "in best_channels),"
            ),
            "v352 conclusion",
        ),
        (
            (
                'md = "# Ar-He-H Deep Hybrid '
                'Tests — Summary\\n\\n"'
            ),
            (
                'md = "# Ar-He-H Monte Carlo '
                'Configuration Screening — '
                'Summary\\n\\n"'
            ),
            "v352 title",
        ),
        (
            (
                'md += f"Total trials: '
                '{len(rows)}\\n\\n"'
            ),
            (
                'md += f"Total screening '
                'trials: {len(rows)}\\n\\n"'
            ),
            "v352 trials",
        ),
        (
            (
                'md += "## Best '
                'channels\\n\\n"'
            ),
            (
                'md += "## Configured channel '
                'ranking\\n\\n"'
            ),
            "v352 heading",
        ),
    ]

    for old, new, label in replacements:
        text = replace_once(
            text,
            old,
            new,
            label,
        )

    write(
        path,
        text,
    )

    smoke = (
        root
        / "tests/smoke_test.py"
    )

    text = replace_once(
        read(smoke),
        'assert s["trials"] >= 500',
        lines(
            'assert s["trials"] == 720',
            (
                'assert s["model_class"] == '
                '"monte_carlo_configuration_'
                'screening"'
            ),
            (
                'assert s["configured_channel_'
                'ranking"] == ['
            ),
            '    "em_only",',
            '    "hybrid_em_retention",',
            '    "hybrid_balanced",',
            '    "hybrid_soft",',
            '    "acoustic_only",',
            "]",
            (
                'assert s["outcomes"]'
                '["screening_candidate"] == 242'
            ),
        ),
        "v352 smoke",
    )

    write(
        smoke,
        text,
    )

    append_journal(
        (
            root
            / (
                "journal/"
                "session_journal_v35_2.md"
            )
        ),
        (
            "## Evidence Classification "
            "Correction — 2026-07-29"
        ),
        [
            (
                "The package is classified as "
                "Monte Carlo configuration "
                "screening."
            ),
            (
                "The corrected internal ranking "
                "is led by `em_only`, followed "
                "by `hybrid_em_retention` and "
                "`hybrid_balanced`."
            ),
        ],
    )

    run_package(
        root,
        (
            "scripts/"
            "engine_v35_2_ar_he_h_"
            "deep_hybrid_tests.py"
        ),
    )


def patch_v353(
    root: Path,
    v352: Path,
) -> None:
    embedded = (
        root
        / "experiment_v35_2"
    )

    if embedded.exists():
        shutil.rmtree(
            embedded
        )

    shutil.copytree(
        v352,
        embedded,
    )

    write(
        root / "HYBRID_RETENTION_THEOREM.txt",
        lines(
            (
                "HYBRID RETENTION PRINCIPLE "
                "(Ar–He–H Plasma)"
            ),
            "",
            (
                "The theorem preserves a "
                "candidate channel-separation "
                "architecture."
            ),
            "",
            "Embedded v35.2 ranking:",
            "",
            (
                "em_only → "
                "hybrid_em_retention → "
                "hybrid_balanced → "
                "hybrid_soft → acoustic_only"
            ),
            "",
            (
                "The embedded package is a "
                "Monte Carlo configuration-"
                "screening model and does not "
                "dynamically validate physical "
                "channel superiority."
            ),
        ),
    )

    write(
        root / "README.txt",
        lines(
            (
                "v35.3 HYBRID RETENTION "
                "THEOREM PACKAGE"
            ),
            "",
            (
                "Contains the theorem text and "
                "the corrected v35.2 screening "
                "package."
            ),
        ),
    )

    write_manifest(
        root,
        "SHA256SUMS.txt",
    )

    verify_manifest(
        root,
        "SHA256SUMS.txt",
    )


def patch_final(root: Path) -> None:
    readme = (
        root
        / "README.md"
    )

    text = replace_once(
        read(readme),
        "→ experimental validation",
        (
            "→ computational evidence "
            "classification"
        ),
        "final proof chain",
    )

    text += "\n\n" + lines(
        (
            "## Computational Evidence "
            "Boundary"
        ),
        "",
        (
            "v35 is design-space "
            "prioritization, v35.1 is "
            "engineering scoring, v35.2 is "
            "Monte Carlo configuration "
            "screening, and v35.3 preserves "
            "the theorem with embedded "
            "screening evidence."
        ),
        "",
        (
            "These packages reproduce "
            "configured calculations but do "
            "not provide independent "
            "time-resolved dynamic validation."
        ),
    )

    write(
        readme,
        text,
    )

    index = (
        root
        / "PACKAGE_INDEX.json"
    )

    value = json.loads(
        read(index)
    )

    value["evidence_status"] = {
        (
            "v35"
        ): (
            "deterministic_design_space_"
            "prioritization_matrix"
        ),
        (
            "v35_1"
        ): (
            "deterministic_engineering_"
            "design_scoring"
        ),
        (
            "v35_2"
        ): (
            "monte_carlo_configuration_"
            "screening"
        ),
        (
            "v35_3"
        ): (
            "theorem_package_with_embedded_"
            "screening_evidence"
        ),
    }

    write_json(
        index,
        value,
    )

    theorem = (
        root
        / "theorems/hybrid_retention_theorem.md"
    )

    write(
        theorem,
        lines(
            "# Hybrid Retention Theorem",
            "",
            (
                "The theorem defines a candidate "
                "channel-separation architecture."
            ),
            "",
            (
                "Corrected v35.2 screening "
                "anchor:"
            ),
            "",
            "screening_candidate: 242",
            "",
            (
                "em_only → "
                "hybrid_em_retention → "
                "hybrid_balanced → "
                "hybrid_soft → acoustic_only"
            ),
            "",
            (
                "The screening ranking does not "
                "dynamically validate physical "
                "channel superiority."
            ),
        ),
    )

    report = (
        root
        / (
            "validation/"
            "package_integrity_report.json"
        )
    )

    value = json.loads(
        read(report)
    )

    value["status"] = (
        "evidence_classification_"
        "corrected_and_rechecked"
    )

    write_json(
        report,
        value,
    )

    write_manifest(
        root,
        "checksums/SHA256SUMS.txt",
    )

    verify_manifest(
        root,
        "checksums/SHA256SUMS.txt",
    )


def verify_results(
    v35: Path,
    v351: Path,
    v352: Path,
    v353: Path,
    final: Path,
) -> None:
    s35 = json.loads(
        read(
            v35
            / (
                "results/"
                "hybrid_multi_gas_regime_"
                "matrix_summary.json"
            )
        )
    )

    if (
        s35["model_class"]
        != (
            "deterministic_design_space_"
            "prioritization_matrix"
        )
    ):
        raise SystemExit(
            "v35 classification mismatch"
        )

    s351 = json.loads(
        read(
            v351
            / (
                "results/"
                "ar_he_h_acoustic_em_"
                "retention_summary.json"
            )
        )
    )

    if (
        s351["model_class"]
        != (
            "deterministic_engineering_"
            "design_scoring"
        )
    ):
        raise SystemExit(
            "v351 classification mismatch"
        )

    s352 = json.loads(
        read(
            v352
            / (
                "results/"
                "ar_he_h_deep_hybrid_"
                "tests_summary.json"
            )
        )
    )

    expected = [
        "em_only",
        "hybrid_em_retention",
        "hybrid_balanced",
        "hybrid_soft",
        "acoustic_only",
    ]

    if (
        s352[
            "configured_channel_ranking"
        ]
        != expected
    ):
        raise SystemExit(
            "v352 ranking mismatch: "
            f"{s352['configured_channel_ranking']}"
        )

    if (
        s352["outcomes"].get(
            "screening_candidate"
        )
        != 242
    ):
        raise SystemExit(
            "v352 screening count mismatch"
        )

    embedded = json.loads(
        read(
            v353
            / (
                "experiment_v35_2/"
                "results/"
                "ar_he_h_deep_hybrid_"
                "tests_summary.json"
            )
        )
    )

    if (
        embedded[
            "configured_channel_ranking"
        ]
        != expected
    ):
        raise SystemExit(
            "v353 embedded ranking mismatch"
        )

    final_text = read(
        final
        / (
            "theorems/"
            "hybrid_retention_theorem.md"
        )
    )

    for marker in [
        "screening_candidate: 242",
        "em_only",
        "does not dynamically validate",
    ]:
        if marker not in final_text:
            raise SystemExit(
                "Final theorem marker missing: "
                f"{marker}"
            )


def verify_zip(path: Path) -> None:
    with zipfile.ZipFile(
        path,
        "r",
    ) as archive:
        damaged = archive.testzip()

        if damaged:
            raise SystemExit(
                "ZIP integrity failure: "
                f"{path.name}/{damaged}"
            )


def main() -> None:
    verify_source()

    historical = sorted(
        (
            ROOT
            / (
                "experimental_"
                "historical_archive"
            )
        ).glob(
            "*.zip"
        )
    )

    if not historical:
        raise SystemExit(
            "No historical ZIP archives found"
        )

    historical_hashes = {
        path: sha256(path)
        for path in historical
    }

    correct_root()

    with tempfile.TemporaryDirectory(
        prefix="rwr-correction-"
    ) as temporary:
        temp = Path(temporary)

        roots = {
            name: temp / name
            for name in PACKAGES
        }

        for (
            key,
            (
                name,
                _,
            ),
        ) in PACKAGES.items():
            safe_extract(
                ROOT / name,
                roots[key],
            )

        patch_v35(
            roots["v35"]
        )

        patch_v351(
            roots["v351"]
        )

        patch_v352(
            roots["v352"]
        )

        patch_v353(
            roots["v353"],
            roots["v352"],
        )

        patch_final(
            roots["final"]
        )

        verify_results(
            roots["v35"],
            roots["v351"],
            roots["v352"],
            roots["v353"],
            roots["final"],
        )

        for (
            key,
            (
                name,
                _,
            ),
        ) in PACKAGES.items():
            pack(
                roots[key],
                ROOT / name,
            )

    for (
        path,
        expected,
    ) in historical_hashes.items():
        if sha256(path) != expected:
            raise SystemExit(
                "Historical archive changed: "
                f"{path}"
            )

    for (
        name,
        _,
    ) in PACKAGES.values():
        verify_zip(
            ROOT / name
        )

    readme = read(
        ROOT / "README.md"
    )

    for required in [
        "C ~ v^(1/4)",
        "t_delay ~ v^(−1/2)",
        (
            "## Computational Evidence "
            "Boundary"
        ),
    ]:
        if required not in readme:
            raise SystemExit(
                "README marker missing: "
                f"{required}"
            )

    for forbidden in [
        "t_delay ~ v^(−1/3)",
        (
            "hybrid acoustic/"
            "electromagnetic plasma "
            "retention experiments"
        ),
    ]:
        if forbidden in readme:
            raise SystemExit(
                "README stale marker remains: "
                f"{forbidden}"
            )

    print(
        "Evidence classification and cubic "
        "scaling correction completed and "
        "verified."
    )


if __name__ == "__main__":
    main()
