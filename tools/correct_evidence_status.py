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
FIXED_ZIP_TIME = (2026, 7, 29, 0, 0, 0)

PACKAGE_HASHES = {
    "resonance_system_v35_HYBRID_MULTI_GAS_REGIME_MATRIX_TRUE.zip": "9d40616122a1f2c7c37f2430eab3ef7641f1ac62aa457ed49e0931084b9a1f0b",
    "resonance_system_v35_1_AR_HE_HYBRID_ACOUSTIC_EM_RETENTION_TRUE.zip": "8d243c99caeadfd8721ccf6f84496a114b2d94c634d30f22a62b7701a66facce",
    "resonance_system_v35_2_AR_HE_H_DEEP_HYBRID_TESTS_TRUE.zip": "f9e73277a380ca8cbe16883fac5384a0eb8c76e760a731eca4a95c0a62e79a2c",
    "resonance_system_v35_3_HYBRID_RETENTION_THEOREM_PACKAGE_TRUE.zip": "d30e802f5b9db8a1816df79ff4fc750108760d12835563b5877eeb70cc1f9295",
    "FINAL_THEOREM_PACKAGE_REBUILT_TRUE.zip": "0cd53bf53764243ea81d2c4eeafc86efdc92a7bcf08d62a3b43ee76710bbdf74",
}

V35, V351, V352, V353, FINAL = PACKAGE_HASHES

ROOT_MARKERS = {
    "README.md": [
        "This repository presents a theoretical and computational framework",
        "hybrid acoustic/electromagnetic plasma retention experiments",
        "experimental validation architecture for broader resonance-retention dynamics",
    ],
    "experimental_historical_archive/README.md": [
        "# Experimental Proof-Chain",
        "# Hybrid Validation Logic",
        "hybrid driving improves retained organization over time",
    ],
    "theorems/README.md": [
        "# Hybrid Retention Theorem\n\n## Statement",
        "F_acoustic → initiates entry into the resonance window",
        "F_EM → stabilizes Ω_ret",
    ],
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


def block(lines: list[str]) -> str:
    return "\n".join(lines)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 occurrence, found {count}")
    return text.replace(old, new)


def verify_source() -> None:
    if (ROOT / "EVIDENCE_STATUS.md").exists():
        raise SystemExit("EVIDENCE_STATUS.md already exists; correction may already be applied")

    for name, expected in PACKAGE_HASHES.items():
        path = ROOT / name
        if not path.is_file():
            raise SystemExit(f"Missing package: {name}")
        actual = sha256(path)
        if actual != expected:
            raise SystemExit(
                f"Package hash mismatch: {name}\nexpected {expected}\nactual   {actual}"
            )

    for name, markers in ROOT_MARKERS.items():
        path = ROOT / name
        if not path.is_file():
            raise SystemExit(f"Missing document: {name}")
        text = read(path)
        for marker in markers:
            if text.count(marker) != 1:
                raise SystemExit(f"Document marker mismatch in {name}: {marker}")


def safe_extract(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            rel = Path(member.filename)
            if rel.is_absolute() or ".." in rel.parts:
                raise SystemExit(f"Unsafe ZIP member: {zip_path.name}/{member.filename}")
        archive.extractall(destination)


def pack(source: Path, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in source.rglob("*") if p.is_file()):
            rel = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(rel, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            mode = 0o755 if path.suffix == ".py" else 0o644
            info.external_attr = (mode & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())
    os.replace(temporary, destination)


def write_manifest(root: Path, relative_manifest: str) -> None:
    manifest = root / relative_manifest
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel != relative_manifest:
            rows.append(f"{sha256(path)}  {rel}")
    write(manifest, "\n".join(rows))


def verify_manifest(root: Path, relative_manifest: str) -> None:
    for row in read(root / relative_manifest).splitlines():
        if not row.strip():
            continue
        expected, rel = row.split("  ", 1)
        actual = sha256(root / rel)
        if actual != expected:
            raise SystemExit(f"Manifest mismatch: {relative_manifest}: {rel}")


def run_package(root: Path, engine: str, smoke: str) -> None:
    engine_run = subprocess.run(
        [sys.executable, engine, "--outdir", "results"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    write(root / "logs/engine_stdout.txt", engine_run.stdout)
    write(root / "logs/engine_stderr.txt", engine_run.stderr)
    if engine_run.returncode != 0:
        raise SystemExit(f"Engine failed in {root.name}: {engine_run.stderr}")

    smoke_run = subprocess.run(
        [sys.executable, smoke],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    write(root / "logs/smoke_stdout.txt", smoke_run.stdout)
    write(root / "logs/smoke_stderr.txt", smoke_run.stderr)
    if smoke_run.returncode != 0:
        raise SystemExit(f"Smoke test failed in {root.name}: {smoke_run.stderr}")

    write_manifest(root, "checksums/sha256_manifest.txt")
    verify_manifest(root, "checksums/sha256_manifest.txt")


def correct_root_documents() -> None:
    readme_path = ROOT / "README.md"
    text = read(readme_path)
    intro = (
        "This repository presents a theoretical and computational framework for "
        "resonance-driven self-organization, coherent accumulation, retained "
        "operational regimes, and dynamic synthesis in nonlinear dissipative open "
        "dynamic systems."
    )
    boundary = block([
        "## Computational Evidence Boundary",
        "",
        "The formal theorem layer and the computational package layer have different evidential functions.",
        "",
        "The active v35, v35.1, and v35.2 packages are design-space prioritization, engineering scoring, and Monte Carlo configuration-screening models.",
        "",
        "They reproduce configured calculations but do not independently integrate a plasma or oscillator state through time. They therefore do not constitute time-resolved dynamic validation of acoustic, electromagnetic, or hybrid channel superiority.",
        "",
        "The v35.3 package preserves the Hybrid Retention Theorem with the corrected v35.2 screening package. Historical ZIP archives remain unchanged.",
        "",
        "See [EVIDENCE_STATUS.md](EVIDENCE_STATUS.md).",
    ])
    text = replace_once(text, intro, intro + "\n\n" + boundary, "root README boundary")
    text = replace_once(
        text,
        "- and hybrid acoustic/electromagnetic plasma retention experiments.",
        "- and hybrid acoustic/electromagnetic design-scoring and configuration-screening packages.",
        "root README classification",
    )
    text = replace_once(
        text,
        "The hybrid plasma model therefore functions as an experimental validation architecture for broader resonance-retention dynamics in nonlinear dissipative open dynamic systems.",
        "The hybrid plasma model therefore functions as an engineering hypothesis and candidate control architecture. The active v35-series packages rank configured candidates but do not independently validate the physical channel roles.",
        "root README evidence claim",
    )
    write(readme_path, text)

    historical_path = ROOT / "experimental_historical_archive/README.md"
    text = read(historical_path)
    text = replace_once(text, "# Experimental Proof-Chain", "# Historical Computational Proof-Chain", "historical title")
    text = replace_once(
        text,
        "This section contains the experimental validation structure of the framework for nonlinear dissipative open dynamic systems.",
        "This section preserves the historical computational proof-chain of the framework for nonlinear dissipative open dynamic systems.",
        "historical opening",
    )
    old = block([
        "# Hybrid Validation Logic",
        "",
        "The experimental framework validates the separation between:",
        "",
        "entry mechanisms",
        "",
        "and",
        "",
        "retention mechanisms.",
        "",
        "The simulations demonstrate that:",
        "",
        "- acoustic forcing accelerates resonance-window entry",
        "",
        "- electromagnetic stabilization suppresses dispersion",
        "",
        "- hybrid driving improves retained organization over time",
    ])
    new = block([
        "# Historical Hybrid Hypothesis",
        "",
        "The archived packages encode and explore a proposed separation between entry and retention mechanisms.",
        "",
        "The historical channel assignments were:",
        "",
        "- acoustic forcing as a candidate resonance-window entry mechanism",
        "",
        "- electromagnetic forcing as a candidate dispersion-suppression and retention mechanism",
        "",
        "- hybrid driving as a candidate combined control architecture",
        "",
        "These assignments are hypotheses embedded in the historical configurations. They are not independently established by the active v35-series scoring and screening packages.",
    ])
    text = replace_once(text, old, new, "historical hybrid block")
    text += "\n\n" + block([
        "# Historical Evidence Boundary",
        "",
          "The ZIP archives in this directory remain byte-for-byte unchanged.",
        "",
        "The cited v30, v31, and v33 generations do not include matched `F_ext = 0` controls in the published package series; many cited coupling regimes are strongly supercritical; legacy `C` fields are model-specific `R`-dependent proxies; and the cyclic-frequency / angular-frequency convention requires correction in a successor engine.",
        "",
        "These archives document model evolution and executable history. They are not current independent validation evidence for external-forcing retention.",
    ])
    write(historical_path, text)

    theorem_path = ROOT / "theorems/README.md"
    text = read(theorem_path)
    text = replace_once(
        text,
        "# Hybrid Retention Theorem\n\n## Statement",
        block([
            "# Hybrid Retention Theorem",
            "",
            "## Evidence Boundary",
            "",
            "The theorem defines a candidate channel-separation architecture. The active v35.1 scoring package and v35.2 Monte Carlo screening package evaluate configured assumptions; they do not provide independent time-resolved dynamic validation of acoustic entry, electromagnetic retention, or hybrid superiority.",
            "",
            "## Statement",
        ]),
        "theorem boundary",
    )
    text = replace_once(
        text,
        "F_acoustic → initiates entry into the resonance window → accelerates Θ_N accumulation",
        "F_acoustic → candidate role: resonance-window entry and Θ_N accumulation",
        "theorem acoustic role",
    )
    text = replace_once(
        text,
        "F_EM → stabilizes Ω_ret → suppresses phase dispersion → maintains retained organization",
        "F_EM → candidate role: Ω_ret stabilization, phase-dispersion suppression, and retained organization",
        "theorem EM role",
    )
    write(theorem_path, text)

    write(
        ROOT / "EVIDENCE_STATUS.md",
        block([
            "# Computational Evidence Status",
            "",
            "## Active Package Classification",
            "",
            "| Package | Classification | Evidential function |",
            "|---|---|---|",
            "| v35 | deterministic design-space prioritization matrix | ranks configured gas and sequence candidates |",
            "| v35.1 | deterministic engineering design scoring | ranks configured channels, sequences, and a candidate protocol |",
            "| v35.2 | Monte Carlo configuration screening | propagates configured coefficients and seeded perturbations through algebraic screening rules |",
            "| v35.3 | theorem package with embedded corrected v35.2 screening evidence | preserves the theorem and its computational boundary |",
            "| FINAL_THEOREM_PACKAGE_REBUILT_TRUE | publication core with corrected evidence classification | separates formal results from screening evidence |",
            "",
            "## Corrected v35.2 Ranking",
            "",
            "    em_only",
            "    → hybrid_em_retention",
            "    → hybrid_balanced",
            "    → hybrid_soft",
            "    → acoustic_only",
            "",
            "This ranking is internal to the configured screening equations. It is not a measurement of physical channel superiority.",
            "",
            "## Historical Archive Status",
            "",
            "Historical ZIP files remain unchanged. The cited v30, v31, and v33 generations lack matched `F_ext = 0` controls in the published series, use predominantly supercritical coupling in the cited calibrations, contain legacy `C` proxies strongly dependent on `R`, and require an explicit frequency-unit correction in a successor engine.",
            "",
            "## Successor Dynamic Evidence Requirements",
            "",
            "- explicit time integration of state variables",
            "",
            "- matched `F_ext = 0` controls for every parameter point and seed",
            "",
            "- coupling regimes near the applicable critical threshold",
            "",
            "- one frequency convention throughout equations, code, and reports",
            "",
            "- separate diagnostics for phase order, general coherence, and endogenous contribution",
            "",
            "- post-drive comparison against control over a defined retention interval",
        ]),
    )


def patch_v35(root: Path) -> None:
    config_path = root / "configs/config.json"
    cfg = json.loads(read(config_path))
    cfg["model_class"] = "deterministic_design_space_prioritization_matrix"
    cfg["evidence_scope"] = "configured_candidate_ranking_not_dynamic_validation"
    write_json(config_path, cfg)

    write(root / "docs/README.md", block([
        "# v35 — Hybrid Multi-Gas Design-Space Prioritization",
        "",
        "## Classification",
        "",
        "    deterministic design-space prioritization matrix",
        "",
        "This package ranks configured gas and sequence candidates. It does not integrate plasma dynamics through time and does not constitute dynamic validation.",
        "",
        "## Candidate Set",
        "",
        "    Argon → Helium → Hydrogen → Oxygen → Methane → Carbon Dioxide",
        "",
        "## Theorem Reference",
        "",
        "    R is an indicator.",
        "    Θ_N is the admission criterion.",
        "    Retention completes the window.",
        "    Chemistry loss can close the window.",
        "",
        "The criteria above are references for later dynamic testing; they are not dynamically evaluated by this matrix.",
        "",
        "## Run",
        "",
        "    python scripts/engine_v35_hybrid_multi_gas_regime_matrix.py --outdir results",
        "    python tests/smoke_test.py",
    ]))

    write(root / "model/equations_v35.md", block([
        "# v35 Configured Prioritization Equations",
        "",
        "Ω(t) → Ω(t, μ_env, χ_mix)",
        "",
        "    gas_priority = f(retention, legacy_reference_ratio, response_speed, dissipation_risk, chemistry_risk)",
        "",
        "    sequence_priority = g(gas_priority, pair contrast, retention floor, chemistry load)",
        "",
        "    screening_status = candidate_for_dynamic_testing",
        "",
        "The status marks a configured candidate only. It is not a dynamically validated resonance window.",
    ]))

    script_path = root / "scripts/engine_v35_hybrid_multi_gas_regime_matrix.py"
    script = read(script_path)
    script = replace_once(script, '"expected_mode": "hybrid_window_candidate" if sc > 0.35 else "requires_strict_mu_env_calibration"', '"screening_status": "candidate_for_dynamic_testing" if sc > 0.35 else "requires_additional_configuration_review"', "v35 status")
    script = replace_once(script, '"system_class": cfg["system_class"],', '"system_class": cfg["system_class"],\n        "model_class": cfg["model_class"],\n        "evidence_scope": cfg["evidence_scope"],', "v35 metadata")
    script = replace_once(script, '"main_conclusion": "hybrid_regime_should_use_inertial_buffer_plus_fast_probe_plus_molecular_calibration",', '"main_conclusion": "configured_design_space_priority_is_" + "_then_".join(seqs[0]["sequence"]),', "v35 conclusion")
    script = replace_once(script, '"reason": "highest score under retention/response/dissipation/chemistry balance"', '"reason": "highest configured score; requires independent dynamic testing"', "v35 reason")
    script = replace_once(script, '"theorem_note": "For hybrid gas mixtures Ω(t) must be extended to Ω(t, μ_env, χ_mix), where μ_env captures medium parameters and χ_mix captures mixture composition."', '"theorem_note": "The matrix prioritizes configured candidates and does not validate a physical resonance window."', "v35 note")
    script = replace_once(script, 'mode={s[\'expected_mode\']}', 'status={s[\'screening_status\']}', "v35 markdown status")
    write(script_path, script)

    smoke_path = root / "tests/smoke_test.py"
    smoke = read(smoke_path)
    smoke = replace_once(smoke, 'assert "hybrid_sequence_rank" in s', 'assert "hybrid_sequence_rank" in s\nassert s["model_class"] == "deterministic_design_space_prioritization_matrix"\nassert all("expected_mode" not in row for row in s["hybrid_sequence_rank"])', "v35 smoke")
    write(smoke_path, smoke)

    run_package(root, "scripts/engine_v35_hybrid_multi_gas_regime_matrix.py", "tests/smoke_test.py")


def patch_v351(root: Path) -> None:
    config_path = root / "configs/config.json"
    cfg = json.loads(read(config_path))
    cfg["model_class"] = "deterministic_engineering_design_scoring"
    cfg["evidence_scope"] = "configured_channel_and_sequence_ranking_not_dynamic_validation"
    write_json(config_path, cfg)

    write(root / "docs/README.md", block([
        "# v35.1 — Ar-He-H Acoustic + Electromagnetic Engineering Scoring",
        "",
        "## Classification",
        "",
        "    deterministic engineering design scoring",
        "",
        "This package scores the configured hypothesis:",
        "",
        "    acoustic entry + electromagnetic retention",
        "",
        "for the candidate sequence:",
        "",
        "    Argon → Helium → Hydrogen",
        "",
        "The package does not integrate phase variables, fields, or a plasma state through time. Its ranking is produced from configured gas and channel coefficients.",
        "",
        "The four-phase protocol remains a candidate engineering protocol, not a dynamically simulated validation sequence.",
        "",
        "## Run",
        "",
        "    python scripts/engine_v35_1_ar_he_h_acoustic_em_retention.py --outdir results",
        "    python tests/smoke_test.py",
    ]))

    write(root / "model/equations_v35_1.md", block([
        "# v35.1 Configured Engineering Scoring",
        "",
        "F_total(t) = F_acoustic(t) + F_EM(t)",
        "",
        "Θ_N = Σ W_period(k)",
        "",
        "The package evaluates a configured engineering score. It does not compute a time-resolved Θ_N trajectory, retained-domain membership, or post-drive dynamics.",
    ]))

    script_path = root / "scripts/engine_v35_1_ar_he_h_acoustic_em_retention.py"
    script = read(script_path)
    script = replace_once(script, '"system_class": cfg["system_class"],', '"system_class": cfg["system_class"],\n        "model_class": cfg["model_class"],\n        "evidence_scope": cfg["evidence_scope"],', "v351 metadata")
    script = replace_once(script, '"main_conclusion": "best_engineering_path_is_argon_buffer_with_acoustic_entry_and_em_retention_for_helium_hydrogen_transfer",', '"main_conclusion": "configured_scoring_ranks_" + seq_results[0]["best_channel"] + "_for_" + "_then_".join(seq_results[0]["sequence"]),', "v351 conclusion")
    script = replace_once(script, '"theorem_note": "Hybrid control separates entry channel from retention channel: acoustic drive is economical for Θ_N initiation, electromagnetic drive is superior for Ω_ret stabilization."', '"theorem_note": "The channel-role separation is a configured engineering hypothesis. This package scores it and does not dynamically validate it."', "v351 note")
    write(script_path, script)

    smoke_path = root / "tests/smoke_test.py"
    smoke = read(smoke_path)
    smoke = replace_once(smoke, 'assert "operational_protocol" in s', 'assert "operational_protocol" in s\nassert s["model_class"] == "deterministic_engineering_design_scoring"', "v351 smoke")
    write(smoke_path, smoke)

    run_package(root, "scripts/engine_v35_1_ar_he_h_acoustic_em_retention.py", "tests/smoke_test.py")


def patch_v352(root: Path) -> None:
    config_path = root / "configs/config.json"
    cfg = json.loads(read(config_path))
    cfg["model"] = "Ar-He-H Monte Carlo configuration screening matrix"
    cfg["model_class"] = "monte_carlo_configuration_screening"
    cfg["evidence_scope"] = "algebraic_candidate_screening_not_time_resolved_dynamic_validation"
    write_json(config_path, cfg)

    write(root / "docs/README.md", block([
        "# v35.2 — Ar-He-H Monte Carlo Configuration Screening",
        "",
        "## Classification",
        "",
        "    Monte Carlo configuration screening model",
        "",
        "This package propagates configured gas, channel, stress, and threshold coefficients through algebraic screening equations with seeded random perturbations.",
        "",
        "It does not contain differential equations, time integration, phase-state evolution, or a matched `F_ext = 0` dynamic control. Reproducibility confirms execution of the screening rules, not physical validation of channel superiority.",
        "",
        "## Screening Outcomes",
        "",
        "    phase_alignment_without_work",
        "    accumulation_without_retention",
        "    collapse_after_drive_reduction",
        "    no_window",
        "    screening_candidate",
        "",
        "## Run",
        "",
        "    python scripts/engine_v35_2_ar_he_h_deep_hybrid_tests.py --outdir results",
        "    python tests/smoke_test.py",
    ]))

    write(root / "model/equations_v35_2.md", block([
        "# v35.2 Algebraic Screening Equations",
        "",
        "F_total(t) = F_acoustic(t) + F_EM(t)",
        "",
        "    screening_candidate =",
        "    Θ_N_proxy >= theta_crit",
        "    and balance_proxy >= balance_crit",
        "    and retention_tail_proxy >= retention_min",
        "    and stable_periods_proxy >= stable_periods_min",
        "    and collapse_risk_proxy <= collapse_limit",
        "",
        "A screening candidate requires independent dynamic testing before any validation claim.",
    ]))

    script_path = root / "scripts/engine_v35_2_ar_he_h_deep_hybrid_tests.py"
    script = read(script_path
      script = script.replace("valid_ratio", "candidate_ratio")
    script = replace_once(
        script,
        '"model": cfg["model"],',
        '"model": cfg["model"],\n        "model_class": cfg["model_class"],\n        "evidence_scope": cfg["evidence_scope"],',
        "v352 metadata",
    )
    script = replace_once(
        script,
        '"best_scenarios": best_scenarios,',
        '"best_scenarios": best_scenarios,\n        "configured_channel_ranking": [name for name, _ in best_channels],\n        "ranking_basis": "candidate_ratio, mean_retention_tail, and inverse mean_collapse_risk within the configured algebraic screening model",',
        "v352 ranking metadata",
    )
    script = replace_once(
        script,
        '"main_conclusion": "hybrid_em_retention_and_hybrid_balanced_are_the_best_candidates_for_deep_Ar_He_H_testing",',
        '"main_conclusion": "configured_screening_ranking_is_" + "_then_".join(name for name, _ in best_channels),',
        "v352 conclusion",
    )
    script = replace_once(
        script,
        'md = "# Ar-He-H Deep Hybrid Tests — Summary\\n\\n"',
        'md = "# Ar-He-H Monte Carlo Configuration Screening — Summary\\n\\n"',
        "v352 markdown title",
    )
    script = replace_once(
        script,
        'md += f"Total trials: {len(rows)}\\n\\n"',
        'md += f"Total screening trials: {len(rows)}\\n\\n"',
        "v352 markdown trial label",
    )
    script = replace_once(
        script,
        'md += "## Best channels\\n\\n"',
        'md += "## Configured channel ranking\\n\\n"',
        "v352 markdown channel heading",
    )
    script = replace_once(
        script,
        '(out/"ar_he_h_deep_hybrid_tests_summary.md").write_text(md, encoding="utf-8")',
        'md += "\\n## Evidence boundary\\n\\nThis is an internal ranking of configured screening equations, not time-resolved dynamic validation of physical channel superiority.\\n"\n    (out/"ar_he_h_deep_hybrid_tests_summary.md").write_text(md, encoding="utf-8")',
        "v352 markdown evidence boundary",
    )
    write(script_path, script)

    smoke_path = root / "tests/smoke_test.py"
    smoke = read(smoke_path)
    smoke = replace_once(
        smoke,
        'assert s["trials"] >= 500',
        block([
            'assert s["trials"] == 720',
            'assert s["model_class"] == "monte_carlo_configuration_screening"',
            'assert s["configured_channel_ranking"] == [',
            '    "em_only",',
            '    "hybrid_em_retention",',
            '    "hybrid_balanced",',
            '    "hybrid_soft",',
            '    "acoustic_only",',
            ']',
            'assert s["outcomes"]["screening_candidate"] == 242',
            'assert "valid_hybrid_resonance_window" not in json.dumps(s, ensure_ascii=False)',
        ]),
        "v352 smoke",
    )
    write(smoke_path, smoke)

    journal_path = root / "journal/session_journal_v35_2.md"
    journal = read(journal_path).rstrip()
    journal += "\n\n" + block([
        "## Evidence Classification Correction — 2026-07-29",
        "",
        "The package is classified as Monte Carlo configuration screening.",
        "",
        "The equations compute algebraic proxies from configured coefficients and seeded perturbations.",
        "",
        "The corrected internal ranking is led by `em_only`, followed by `hybrid_em_retention` and `hybrid_balanced`.",
        "",
        "This ranking is not time-resolved dynamic validation of physical channel superiority.",
    ])
    write(journal_path, journal)

    run_package(
        root,
        "scripts/engine_v35_2_ar_he_h_deep_hybrid_tests.py",
        "tests/smoke_test.py",
    )


def patch_v353(root: Path, corrected_v352: Path) -> None:
    embedded = root / "experiment_v35_2"

    if embedded.exists():
        shutil.rmtree(embedded)

    shutil.copytree(
        corrected_v352,
        embedded,
    )

    write(
        root / "HYBRID_RETENTION_THEOREM.txt",
        block([
            "HYBRID RETENTION PRINCIPLE (Ar–He–H Plasma)",
            "",
            "The hybrid regime does not create coherence.",
            "",
            "It defines a candidate control architecture for the temporal persistence of a self-organized state.",
            "",
            "Control:",
            "",
            "F_total(t) = F_acoustic(t) + F_EM(t)",
            "",
            "Formal candidate roles:",
            "",
            "F_acoustic → candidate entry into Ω(t) and Θ_N accumulation",
            "",
            "F_EM → candidate Ω_ret stabilization and retention support",
            "",
            "Core condition:",
            "",
            "Θ_N ≥ Θ_crit",
            "",
            "∫(C − P) dt > 0 over completed periods",
            "",
            "x(t) ∈ Ω_ret for t ≥ t₀ + τ after drive reduction",
            "",
            "Embedded v35.2 screening result:",
            "",
            "em_only → hybrid_em_retention → hybrid_balanced → hybrid_soft → acoustic_only",
            "",
            "Evidence boundary:",
            "",
            "The embedded v35.2 package is a Monte Carlo configuration-screening model. Its ranking is internal to configured algebraic proxies and does not dynamically validate physical channel superiority.",
            "",
            "Independent time-resolved dynamic controls remain required.",
        ]),
    )

    write(
        root / "README.txt",
        block([
            "v35.3 HYBRID RETENTION THEOREM PACKAGE",
            "",
            "Contains:",
            "",
            "- Hybrid Retention Principle text",
            "",
            "- Corrected v35.2 Monte Carlo configuration-screening package",
            "",
            "Formal candidate architecture:",
            "",
            "acoustic entry + EM retention",
            "",
            "Evidence status:",
            "",
            "The embedded package ranks configured candidates and does not provide independent dynamic validation.",
            "",
            "System class:",
            "",
            "nonlinear dissipative open dynamic systems",
        ]),
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
    readme_path = root / "README.md"
    text = read(readme_path)

    text = replace_once(
        text,
        "→ experimental validation",
        "→ computational evidence classification",
        "final README proof chain",
    )

    text += "\n\n" + block([
        "## Computational Evidence Boundary",
        "",
        "The theorem package is distinct from the active v35-series computational packages.",
        "",
        "- v35 is a deterministic design-space prioritization matrix.",
        "",
        "- v35.1 is deterministic engineering design scoring.",
        "",
        "- v35.2 is Monte Carlo configuration screening.",
        "",
        "- v35.3 preserves the theorem with the corrected v35.2 screening package.",
        "",
        "These packages reproduce configured calculations. They do not independently provide time-resolved dynamic validation of acoustic, electromagnetic, or hybrid channel superiority.",
    ])

    write(
        readme_path,
        text,
    )

    index_path = root / "PACKAGE_INDEX.json"
    index = json.loads(read(index_path))

    index["evidence_status"] = {
        "v35": "deterministic_design_space_prioritization_matrix",
        "v35_1": "deterministic_engineering_design_scoring",
        "v35_2": "monte_carlo_configuration_screening",
        "v35_3": "theorem_package_with_embedded_screening_evidence",
        "boundary": "configured_computational_ranking_not_time_resolved_dynamic_validation",
    }

    index["intended_use"] = [
        "GitHub theorem package",
        "Zenodo publication core",
        "index for computational evidence packages",
    ]

    write_json(
        index_path,
        index,
    )

    write(
        root / "experiments_index/experiment_chain.md",
        block([
            "# Computational Evidence Chain",
            "",
            "## Purpose",
            "",
            "The computational chain preserves sequence, reproducibility, model evolution, and evidence classification.",
            "",
            "## Core Packages",
            "",
            "    v35   — deterministic multi-gas design-space prioritization",
            "    v35.1 — deterministic acoustic/EM engineering scoring",
            "    v35.2 — Monte Carlo configuration screening",
            "    v35.3 — Hybrid Retention Theorem with embedded corrected v35.2 screening",
            "",
            "## Supporting Historical Packages",
            "",
            "    v30.3 — Argon Work-Accumulation Recheck",
            "    v31.3 — Helium Work-Accumulation Recheck",
            "    v33.2 — Hydrogen Work-Accumulation Calibration",
            "    v34   — Methane Plasma Profile",
            "    v34.1 — Methane Kuramoto / Work Layer",
            "    v32.1 — Cross-Gas Synthesis Map",
            "",
            "## Evidence Logic",
            "",
            "1. Historical packages preserve model development and executable reconstruction.",
            "",
            "2. Work-accumulation conditions define theorem-level acceptance criteria.",
            "",
            "3. v35 and v35.1 prioritize configured engineering candidates.",
            "",
            "4. v35.2 ranks configured channel candidates by algebraic Monte Carlo screening.",
            "",
            "5. Independent dynamic validation requires matched no-drive controls and explicit time integration.",
        ]),
    )

    reproducibility_path = (
        root
        / "experiments_index/reproducibility_matrix.md"
    )

    reproducibility = read(
        reproducibility_path
    ).rstrip()

    reproducibility += "\n\n" + block([
        "## Evidence Rule",
        "",
        "Reproducibility establishes that a package executes and regenerates its configured output.",
        "",
        "It does not by itself establish dynamic or physical validation. The model class, controls, state evolution, and inference boundary must be reported separately.",
    ])

    write(
        reproducibility_path,
        reproducibility,
    )

    write(
        root / "theorems/hybrid_retention_theorem.md",
        block([
            "# Hybrid Retention Theorem",
            "",
            "## System Class",
            "",
            "    nonlinear dissipative open dynamic systems",
            "",
            "## Core Statement",
            "",
            "The theorem defines a candidate architecture that separates entry and retention mechanisms for the temporal stability of self-organized plasma states.",
            "",
            "## Control Architecture",
            "",
            "    F_total(t) = F_acoustic(t) + F_EM(t)",
            "",
            "with formally assigned candidate roles:",
            "",
            "    F_acoustic → candidate entry into Ω(t) and initiation of Θ_N accumulation",
            "",
            "    F_EM → candidate Ω_ret stabilization and retention support",
            "",
            "## Retention Condition",
            "",
            "    Θ_N ≥ Θ_crit",
            "",
            "and",
            "",
            "    ∫(C(t) − P(t)) dt > 0",
            "",
            "over completed periods, with retained-domain membership after drive reduction.",
            "",
            "## Computational Screening Anchor",
            "",
            "Corrected v35.2 configuration screening:",
            "",
            "    total screening trials: 720",
            "",
            "    screening_candidate: 242",
            "    accumulation_without_retention: 466",
            "    phase_alignment_without_work: 10",
            "    no_window: 2",
            "",
            "    configured channel ranking:",
            "",
            "    em_only",
            "    → hybrid_em_retention",
            "    → hybrid_balanced",
            "    → hybrid_soft",
            "    → acoustic_only",
            "",
            "## Evidence Boundary",
            "",
            "The v35.2 package computes algebraic proxies from configured coefficients and seeded perturbations. The ranking above is internal to that screening model and does not dynamically validate physical channel superiority.",
            "",
            "The theorem-level channel separation remains a research hypothesis requiring independent time-resolved testing with matched no-drive controls.",
        ]),
    )

    report_path = (
        root
        / "validation/package_integrity_report.json"
    )

    report = json.loads(
        read(report_path)
    )

    report["file_count"] = len([
        path
        for path in root.rglob("*")
        if path.is_file()
    ])

    report["status"] = (
        "evidence_classification_"
        "corrected_and_rechecked"
    )

    write_json(
        report_path,
        report,
    )

    write_manifest(
        root,
        "checksums/SHA256SUMS.txt",
    )

    verify_manifest(
        root,
        "checksums/SHA256SUMS.txt",
    )


def verify_outputs(
    v35: Path,
    v351: Path,
    v352: Path,
    v353: Path,
    final: Path,
) -> None:
    summary35 = json.loads(
        read(
            v35
            / "results/hybrid_multi_gas_regime_matrix_summary.json"
        )
    )

    if (
        summary35["model_class"]
        != "deterministic_design_space_prioritization_matrix"
    ):
        raise SystemExit(
            "v35 classification verification failed"
        )

    if any(
        "expected_mode" in row
        for row in summary35["hybrid_sequence_rank"]
    ):
        raise SystemExit(
            "v35 stale expected_mode remains"
        )

    summary351 = json.loads(
        read(
            v351
            / "results/ar_he_h_acoustic_em_retention_summary.json"
        )
    )

    if (
        summary351["model_class"]
        != "deterministic_engineering_design_scoring"
    ):
        raise SystemExit(
            "v35.1 classification verification failed"
        )

    summary352 = json.loads(
        read(
            v352
            / "results/ar_he_h_deep_hybrid_tests_summary.json"
        )
    )

    expected_ranking = [
        "em_only",
        "hybrid_em_retention",
        "hybrid_balanced",
        "hybrid_soft",
        "acoustic_only",
    ]

    if (
        summary352["configured_channel_ranking"]
        != expected_ranking
    ):
        raise SystemExit(
            "v35.2 ranking mismatch: "
            f"{summary352['configured_channel_ranking']}"
        )

    if (
        summary352["outcomes"].get(
            "screening_candidate"
        )
        != 242
    ):
        raise SystemExit(
            "v35.2 screening-candidate count mismatch"
        )

    if (
        "valid_hybrid_resonance_window"
        in json.dumps(
            summary352,
            ensure_ascii=False,
        )
    ):
        raise SystemExit(
            "v35.2 stale validation outcome remains"
        )

    embedded = json.loads(
        read(
            v353
            / (
                "experiment_v35_2/results/"
                "ar_he_h_deep_hybrid_tests_summary.json"
            )
        )
    )

    if (
        embedded["configured_channel_ranking"]
        != expected_ranking
    ):
        raise SystemExit(
            "v35.3 embedded ranking mismatch"
        )

    final_theorem = read(
        final
        / "theorems/hybrid_retention_theorem.md"
    )

    for marker in [
        "screening_candidate: 242",
        "em_only",
        (
            "does not dynamically validate "
            "physical channel superiority"
        ),
    ]:
        if marker not in final_theorem:
            raise SystemExit(
                f"Final theorem missing marker: {marker}"
            )

    verify_manifest(
        v35,
        "checksums/sha256_manifest.txt",
    )

    verify_manifest(
        v351,
        "checksums/sha256_manifest.txt",
    )

    verify_manifest(
        v352,
        "checksums/sha256_manifest.txt",
    )

    verify_manifest(
        v353,
        "SHA256SUMS.txt",
    )

    verify_manifest(
        final,
        "checksums/SHA256SUMS.txt",
    )


def verify_zip(path: Path) -> None:
    with zipfile.ZipFile(
        path,
        "r",
    ) as archive:
        damaged = archive.testzip()

        if damaged is not None:
            raise SystemExit(
                "ZIP integrity failure in "
                f"{path.name}: {damaged}"
            )


def main() -> None:
    verify_source()

    historical_dir = (
        ROOT
        / "experimental_historical_archive"
    )

    historical_archives = sorted(
        historical_dir.glob("*.zip")
    )

    if not historical_archives:
        raise SystemExit(
            "No historical ZIP archives found"
        )

    historical_hashes = {
        path.relative_to(ROOT).as_posix(): sha256(path)
        for path in historical_archives
    }

    correct_root_documents()

    with tempfile.TemporaryDirectory(
        prefix="rwr-evidence-"
    ) as temporary:
        temp = Path(temporary)

        v35 = temp / "v35"
        v351 = temp / "v351"
        v352 = temp / "v352"
        v353 = temp / "v353"
        final = temp / "final"

        safe_extract(
            ROOT / V35,
            v35,
        )

        safe_extract(
            ROOT / V351,
            v351,
        )

        safe_extract(
            ROOT / V352,
            v352,
        )

        safe_extract(
            ROOT / V353,
            v353,
        )

        safe_extract(
            ROOT / FINAL,
            final,
        )

        patch_v35(v35)
        patch_v351(v351)
        patch_v352(v352)

        patch_v353(
            v353,
            v352,
        )

        patch_final(final)

        verify_outputs(
            v35,
            v351,
            v352,
            v353,
            final,
        )

        pack(
            v35,
            ROOT / V35,
        )

        pack(
            v351,
            ROOT / V351,
        )

        pack(
            v352,
            ROOT / V352,
        )

        pack(
            v353,
            ROOT / V353,
        )

        pack(
            final,
            ROOT / FINAL,
        )

    for rel, expected in historical_hashes.items():
        actual = sha256(
            ROOT / rel
        )

        if actual != expected:
            raise SystemExit(
                "Historical archive changed unexpectedly: "
                f"{rel}"
            )

    for name in [
        V35,
        V351,
        V352,
        V353,
        FINAL,
    ]:
        verify_zip(
            ROOT / name
        )

    print(
        "Evidence classification correction "
        "completed and verified."
    )


if __name__ == "__main__":
    main()
