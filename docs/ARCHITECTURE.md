# Architecture

## Recommended Project Structure

```text
coherent-fmcw-lidar-sim/
│
├─ README.md
├─ pyproject.toml
├─ requirements.txt
├─ TASKS.md
│
├─ docs/
│   ├─ SPEC.md
│   ├─ ARCHITECTURE.md
│   ├─ PHYSICS_MODEL.md
│   ├─ FMCW_MODEL.md
│   ├─ BEAM_MODEL.md
│   ├─ OPTICAL_SYSTEM_MODEL.md
│   ├─ SCANNER_DYNAMICS_MODEL.md
│   ├─ SPECKLE_MODEL.md
│   ├─ MATERIAL_MODEL.md
│   ├─ RECEIVER_MODEL.md
│   ├─ GPU_ACCELERATION_MODEL.md
│   ├─ LENS_CATALOG_FORMAT.md
│   └─ VALIDATION_PLAN.md
│
├─ assets/
│   ├─ stl/
│   ├─ scenes/
│   ├─ materials/
│   └─ lenses/
│
├─ src/
│   └─ lidarsim/
│       ├─ constants.py
│       ├─ coordinates.py
│       ├─ beam/
│       ├─ optics/
│       ├─ scanner/
│       ├─ scene/
│       ├─ materials/
│       ├─ scatter/
│       ├─ fmcw/
│       ├─ receiver/
│       ├─ noise/
│       ├─ processing/
│       ├─ compute/
│       └─ visualization/
│
├─ examples/
└─ tests/
```

## Modules

### `beam/`

Beam representation and propagation models.

Files:

- `beam.py`
- `gaussian_beam.py`
- `line_beam.py`
- `beam_profile.py`
- `beam_frame.py`

### `optics/`

Optical elements and ABCD propagation.

Files:

- `element.py`
- `free_space.py`
- `thin_lens.py`
- `thick_lens.py`
- `aperture.py`
- `flat_mirror.py`
- `scanner_mirror.py`
- `beam_expander.py`
- `abcd.py`
- `optical_system.py`

### `scanner/`

Time-dependent scanner motion.

Files:

- `scanner_base.py`
- `scanner_state.py`
- `scan_pattern.py`
- `galvo_scanner.py`
- `mems_scanner.py`
- `polygon_scanner.py`
- `tilted_polygon_scanner.py`
- `scanner_errors.py`
- `footprint.py`

### `scene/`

STL loading, mesh representation, ray intersection, visible patch detection.

Files:

- `mesh.py`
- `scene.py`
- `stl_loader.py`
- `ray_intersection.py`
- `visible_patch.py`

### `scatter/`

Surface scatterers, roughness model, speckle field summation.

Files:

- `scatterer.py`
- `surface_sampler.py`
- `rough_surface.py`
- `speckle.py`

### `fmcw/`

Chirp definition and beat signal generation.

Files:

- `chirp.py`
- `beat_signal.py`
- `phase_noise.py`
- `waveform.py`

### `receiver/`

Receiver optics, aperture collection, coherent mixer.

Files:

- `receiver.py`
- `receiver_optics.py`
- `aperture_collection.py`
- `coherent_mixer.py`

### `processing/`

FFT, CZT, peak detection, range conversion, point cloud.

Files:

- `fft_processing.py`
- `czt_processing.py`
- `peak_detection.py`
- `range_conversion.py`
- `pointcloud.py`

### `compute/`

Backend abstraction and batching for CPU/GPU.

Files:

- `backend.py`
- `batching.py`
- `gpu_utils.py`
- `kernels/cupy_ops.py`
- `kernels/numba_kernels.py`

## Core Data Flow

```text
ScanPattern → ScannerState → BeamState → Footprint → VisiblePatch
→ ScattererWeights → ComplexField → FMCWSignal → Spectrum → RangePixel
```

## Key Data Classes

Required dataclasses:

- `FMCWChirp`
- `GaussianBeam`
- `BeamState`
- `OpticalSystem`
- `ScannerState`
- `Footprint`
- `Material`
- `Scatterer`
- `Receiver`
- `SimulationConfig`
