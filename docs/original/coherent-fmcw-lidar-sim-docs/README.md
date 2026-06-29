# Coherent FMCW LiDAR Forward Simulator

This project is a Python-based coherent FMCW LiDAR forward simulator.

It combines:

- Gaussian beam propagation with M²
- ABCD matrix optical system modeling
- lens/aperture/mirror/scanner models
- scanner dynamics and time-dependent beam steering
- STL/CAD-based scene visibility
- material-dependent reflection
- rough surface scatterer sampling
- coherent speckle field summation
- FMCW beat signal generation
- FFT/CZT range processing
- range/intensity/speckle/point-cloud visualization
- optional GPU acceleration through backend abstraction

This is **not** a pure ray tracing engine.

Ray tracing is used for:

1. visibility
2. occlusion
3. scanner steering geometry
4. mirror reflection geometry
5. STL hit detection
6. visible surface patch selection

The LiDAR signal is generated from **coherent electric field summation** over surface scatterers.

Core idea:

```text
Scanner motion
    ↓
time-dependent BeamState
    ↓
moving beam footprint on target
    ↓
fixed rough scatterer map
    ↓
changing coherent field sum
    ↓
speckle decorrelation
    ↓
FMCW beat signal per pixel
    ↓
batch FFT
    ↓
range/intensity/speckle image
```

## Development Philosophy

Start with physically validated CPU reference models first. GPU acceleration is added after correctness is established.

Recommended order:

```text
FMCW single target
→ Gaussian beam + M²
→ lens/ABCD/aperture
→ rough surface speckle
→ receiver aperture
→ scanner dynamics
→ scanner-driven speckle decorrelation
→ backend abstraction
→ CuPy batch FFT
→ STL visible patch
→ material model
→ car/mirror/retroreflector scene
→ GPU acceleration for full frame
```

## Important Rules

- Do not treat each STL triangle as one optical scatterer.
- STL triangles are geometry and normal references only.
- Optical scatterers must be sampled separately on visible surface patches.
- Do not sum intensity first if speckle is required.
- Correct speckle calculation:

```text
E_rx = Σ A_i exp(jφ_i)
P_rx = |E_rx|²
```

- Incorrect speckle calculation:

```text
P_rx = Σ P_i
```

- Power and field amplitude must remain distinct:

```text
P ∝ |E|²
E ∝ sqrt(P)
```
