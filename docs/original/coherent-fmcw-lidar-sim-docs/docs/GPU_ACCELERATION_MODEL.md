# GPU Acceleration Model

## Goal

The simulator may evaluate:

- many pixels per frame
- many scatterers per pixel
- many samples per chirp
- many frames
- complex field coherent summation
- FFT per pixel
- material and receiver weighting

Therefore, GPU acceleration must be considered from the beginning.

However, the first implementation must be CPU-correct and testable.

## Backend Strategy

Support multiple compute backends:

1. NumPy CPU backend
2. CuPy GPU backend
3. optional PyTorch backend
4. optional Numba CUDA kernels

GPU backend must be optional.

Basic tests must run with NumPy only.

## Design Rule

Do not hard-code NumPy everywhere in heavy numerical functions.

Use backend abstraction:

```python
xp = get_array_module(backend)
```

Heavy functions should accept:

```python
backend="numpy"
dtype="complex128"
```

## Backend Module

Create:

```text
src/lidarsim/compute/backend.py
```

Required functions:

- `get_array_module(backend)`
- `asarray(x, backend, dtype=None)`
- `to_cpu(x)`
- `synchronize(backend)`
- `is_gpu_backend(backend)`

Supported backends:

- `numpy`
- `cupy`, optional
- `torch`, optional

If CuPy is unavailable and backend is `cupy`, raise a clear ImportError.

## What Should Run on GPU?

GPU acceleration targets:

1. scatterer field calculation
2. coherent summation
3. FMCW beat signal generation
4. FFT over many pixels
5. beam footprint weight calculation
6. receiver aperture weighting
7. range image generation
8. Monte Carlo rough surface simulation

## Main Array Shapes

Let:

- `P`: number of pixels
- `S`: number of scatterers per pixel or patch
- `N`: number of samples per chirp
- `F`: number of frames

Possible arrays:

```text
scatterer_positions: [P, S, 3]
scatterer_ranges: [P, S]
scatterer_amplitudes: [P, S]
scatterer_phases: [P, S]
beat_frequencies: [P, S]
time_samples: [N]
complex_signal: [P, N]
fft_spectrum: [P, N_fft]
```

Naive full signal construction:

```text
signal[p, n] = Σ_s A[p, s] exp(j(2π fb[p, s] t[n] + phi[p, s]))
```

Do not materialize `[P, S, N]` for large simulations.

## Memory Strategy

Use batching.

Process:

- pixels in batches
- scatterers in chunks
- frames sequentially or in small batches

Avoid allocating:

```text
[P, S, N]
```

unless explicitly requested for debugging.

Memory reference:

- complex64 = 8 bytes
- complex128 = 16 bytes

## GPU Implementation Levels

### Level 0: CPU Reference

- NumPy only
- all tests pass
- used as ground truth

### Level 1: Vectorized NumPy

- reduce Python loops
- vectorize per pixel batch

### Level 2: CuPy Backend

- replace NumPy arrays with CuPy arrays
- use `cupy.fft`
- keep arrays on GPU

### Level 3: Numba CUDA Kernels

Use custom kernels for:

- scatterer amplitude/phase calculation
- coherent sum without huge temporary arrays
- beam footprint weighting
- receiver aperture weighting

### Level 4: C++/CUDA Extension

Only if Python GPU is insufficient.

## Precision Policy

Default:

- CPU validation: complex128
- GPU performance: complex64

Validation:

- compare FFT peak index
- compare normalized spectrum within tolerance
- compare estimated range within one range bin

## GPU Acceptance Criteria

1. CPU and GPU FFT peak indices match.
2. GPU backend is optional.
3. GPU backend does not change physics model.
4. GPU backend uses batching for large simulations.
5. Core tests pass without GPU.
6. GPU example falls back gracefully if CuPy is unavailable.
