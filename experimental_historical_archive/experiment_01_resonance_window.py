#!/usr/bin/env python3
import numpy as np, json, csv
from pathlib import Path

def simulate(
    N=192, T=6.0, dt=0.006,
    omega_mean=1.0, omega_std=0.10,
    K=0.40,
    F_ext=0.0, omega_ext=1.0, phase_ext=0.0,
    duty_cycle=1.0,
    noise=0.02,
    forcing_off_time=None,
    seed=1,
    R_threshold=0.7,
):
    rng = np.random.default_rng(seed)
    steps = int(T / dt)
    t = np.arange(steps) * dt
    phi = rng.uniform(0, 2*np.pi, size=N)
    omega = rng.normal(omega_mean, omega_std, size=N)
    R_values = np.zeros(steps)
    forcing_values = np.zeros(steps)
    period = 2*np.pi / omega_ext if omega_ext != 0 else T

    for k, tk in enumerate(t):
        z = np.mean(np.exp(1j * phi))
        R = np.abs(z)
        psi = np.angle(z)
        R_values[k] = R

        active = F_ext
        if forcing_off_time is not None and tk >= forcing_off_time:
            active = 0.0
        if duty_cycle < 1.0:
            if ((tk % period) / period) > duty_cycle:
                active = 0.0
        forcing_values[k] = active

        phi += dt * (
            omega
            + K * R * np.sin(psi - phi)
            + active * np.sin(omega_ext * tk + phase_ext - phi)
            + noise * rng.normal(0, 1, size=N)
        )

    above = np.where(R_values >= R_threshold)[0]
    t_conv = float(t[above[0]]) if len(above) else None

    retention_time = None
    if forcing_off_time is not None:
        off_idx = np.searchsorted(t, forcing_off_time)
        after = R_values[off_idx:]
        below = np.where(after < R_threshold)[0]
        retention_time = float(t[off_idx + below[0]] - forcing_off_time) if len(below) else float(T - forcing_off_time)

    R_last = float(np.mean(R_values[int(0.9*steps):]))
    D_proxy = float(np.var(np.diff(R_values[int(0.5*steps):])))
    P_in = float(np.mean(forcing_values**2))
    eta_eff = R_last
    R_net = P_in * eta_eff - D_proxy

    return {
        "metrics": {
            "R_final": float(R_values[-1]),
            "R_max": float(np.max(R_values)),
            "R_mean_last_10pct": R_last,
            "t_conv": t_conv,
            "retention_time": retention_time,
            "D_proxy": D_proxy,
            "P_in": P_in,
            "eta_eff": eta_eff,
            "R_net": R_net,
        },
        "params": {
            "N": N, "T": T, "dt": dt,
            "omega_mean": omega_mean, "omega_std": omega_std,
            "K": K, "F_ext": F_ext,
            "omega_ext": omega_ext,
            "phase_ext": phase_ext,
            "duty_cycle": duty_cycle,
            "noise": noise,
            "forcing_off_time": forcing_off_time,
            "seed": seed,
            "R_threshold": R_threshold,
        }
    }

def run_experiment(out_dir="results"):
    out = Path(out_dir)
    out.mkdir(exist_ok=True)

    base_params = dict(
        N=192, T=6.0, dt=0.006,
        omega_mean=1.0, omega_std=0.10,
        K=0.40, noise=0.02,
        forcing_off_time=4.0,
        R_threshold=0.7,
    )

    baseline = simulate(F_ext=0.0, seed=10, **base_params)
    (out / "baseline.json").write_text(json.dumps(baseline, indent=2), encoding="utf-8")

    rows = []
    omega_values = np.linspace(0.75, 1.25, 11)
    amp_values = [0.08, 0.18, 0.30]
    phase_values = [0.0, np.pi/2]
    duty_values = [1.0, 0.5]

    run_id = 0
    for omega_ext in omega_values:
        for F_ext in amp_values:
            for phase_ext in phase_values:
                for duty_cycle in duty_values:
                    run_id += 1
                    res = simulate(
                        F_ext=F_ext,
                        omega_ext=float(omega_ext),
                        phase_ext=float(phase_ext),
                        duty_cycle=float(duty_cycle),
                        seed=100 + run_id,
                        **base_params
                    )
                    row = {
                        "run_id": run_id,
                        "omega_ext": res["params"]["omega_ext"],
                        "F_ext": res["params"]["F_ext"],
                        "phase_ext": res["params"]["phase_ext"],
                        "duty_cycle": res["params"]["duty_cycle"],
                        **res["metrics"]
                    }
                    rows.append(row)

    rows_sorted = sorted(rows, key=lambda x: (x["R_net"], x["R_mean_last_10pct"]), reverse=True)
    top = rows_sorted[:15]

    for name, data in [("sweep_results.csv", rows), ("top_candidates.csv", top)]:
        with (out / name).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(data)

    (out / "top_candidates.json").write_text(json.dumps(top, indent=2), encoding="utf-8")
    return baseline, top

if __name__ == "__main__":
    baseline, top = run_experiment()
    print("BASELINE")
    print(json.dumps(baseline["metrics"], indent=2))
    print("TOP 5")
    print(json.dumps(top[:5], indent=2))
