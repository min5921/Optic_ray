# Energy Accounting and Numerical Convergence Contract

- Status: Initial implementation contract
- Date: 2026-06-28

## 1. Purpose

The simulator must show where optical power goes and whether results are stable with respect to numerical resolution.

## 2. Power Ledger

Each optical path maintains a ledger:

```text
source power
- source/coupling loss
- aperture clipping
- lens/window/filter loss
- mirror/scanner loss
= target incident power
- absorption/transmission/out-of-path scattering
= modeled reflected/scattered power
× receiver geometric collection
× receiver optical efficiency
= receiver-aperture or detector power
```

Each term records:

- component/surface/path ID;
- input/output power;
- loss in W and dB;
- model/data source;
- validity/warning;
- numerical residual.

## 3. Energy Conservation

For energy-conserving models:

```text
reflected + transmitted + absorbed <= incident + numerical_tolerance
```

BRDF/BSDF lobes must be normalized or explicitly labeled as empirical/non-conserving. Clipping and occlusion must not be counted twice.

## 4. Radiometric Convention

Keep these quantities distinct:

- radiant power: W
- irradiance: W/m²
- radiance: W/(m² sr)
- radiant intensity: W/sr
- BRDF: 1/sr
- field amplitude: proportional to sqrt(W) under the selected normalization

The link-budget implementation must state whether incidence cosine is already included in surface irradiance to prevent double application.

## 5. Convergence Dimensions

Run convergence tests over applicable dimensions:

- STL tessellation/triangle size;
- beam-profile grid resolution;
- footprint quadrature/patch count;
- ray count;
- surface scatterer count;
- time/scan sampling;
- chirp sample rate and FFT length;
- wavelength/angular sampling;
- Monte Carlo sample count;
- batch size/precision/backend.

## 6. Convergence Procedure

```text
run at resolution N
run at refined resolution 2N
compare selected metrics
repeat until error target is met or limit is reached
```

Metrics may include:

- beam radius/divergence;
- clipping loss;
- footprint area/peak irradiance;
- received power;
- scan hit position;
- FFT peak/range;
- speckle statistics.

## 7. Initial Numerical Targets

For ideal analytical validation:

- transform position error: `< 1e-9 m`;
- unit-vector norm error: `< 1e-12`;
- port angular alignment error: `< 1e-9 rad`;
- Gaussian beam-radius relative error: `< 0.1%`;
- normalized power-integral error: `< 0.1%`;
- analytical radiometric-power error: `< 1%`;
- identical-config comparison delta: numerical zero within metric tolerance.

These are software targets, not hardware accuracy claims.

## 8. Mesh-specific Checks

- compare raw/scaled bounds with expected bounds;
- detect open/non-manifold edges;
- report degenerate triangles;
- verify face-normal orientation;
- compare return metrics at two tessellation levels;
- use analytic optical planes for ideal mirrors/lenses when mesh facets would dominate error;
- use STL primarily for target/mechanical geometry unless validated otherwise.

## 9. Sampling and Aliasing

- scanner sampling resolves motion and pixel timing;
- footprint sampling resolves the shortest beam dimension;
- FMCW sample rate satisfies the selected beat-frequency range;
- FFT window/zero-padding does not masquerade as physical resolution;
- random scatterer density is tested for stable statistics;
- parameter sweeps retain consistent sampling where comparison requires it.

## 10. Precision and Backend Checks

- `float64/complex128` CPU result is the reference;
- lower precision reports metric deltas;
- CPU/GPU peak indices and normalized spectra are compared;
- batch-size changes do not change results beyond tolerance;
- deterministic mode and nondeterministic operations are reported.

## 11. Audit Output

Every run produces:

- power ledger;
- conservation residual;
- selected convergence status;
- sampling summary;
- precision/backend summary;
- warnings for unresolved convergence;
- confidence impact.
