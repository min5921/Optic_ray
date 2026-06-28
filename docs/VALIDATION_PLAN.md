# Validation Plan

## Test Philosophy

The simulator must be validated from simple physics cases before complex STL/car scenes.

Do not implement a complex scene before the following validations pass.

## Required Tests

### `test_fmcw_range.py`

R = 10 m target.

Expected:

- FFT peak range is 10 m within one range bin.

### `test_gaussian_beam.py`

Expected:

- M² = 1 divergence ≈ λ/(πw0)
- M² increase increases divergence
- M² increase decreases effective Rayleigh length

### `test_abcd_lens.py`

Expected:

- FreeSpace matrix correct
- ThinLens matrix correct
- q-parameter propagation correct

### `test_aperture_clipping.py`

Expected:

- large aperture gives nearly no loss
- small aperture gives reduced transmitted power

### `test_reflection_law.py`

Expected:

- mirror reflection matches `R = D - 2(D·N)N`
- reflected vector normalized

### `test_speckle_statistics.py`

Expected:

- roughness_rms = 0 gives small amplitude fluctuation
- larger roughness gives larger amplitude fluctuation
- fixed random seed gives reproducible results

### `test_receiver_aperture.py`

Expected:

- scatterers outside FOV are rejected
- larger aperture increases collected power

### `test_scanner_geometry.py`

Expected:

- raster scan hit points cover specified FOV
- triangle scan angle has correct frequency/amplitude
- polygon scanner produces one segment per facet

### `test_fft_peak.py`

Expected:

- known beat frequency maps to correct FFT bin

### `test_material_db.py`

Expected:

- material JSON loads correctly
- missing required fields raise errors

### `test_backend_consistency.py`

Expected:

- NumPy and CuPy peak indices match if CuPy is installed
- test skipped gracefully if CuPy is unavailable

## Acceptance Criteria

### 1st Completion

- Single target FMCW signal
- FFT range estimation
- Gaussian beam with M²
- thin lens ABCD propagation
- aperture clipping
- rough surface speckle
- scanner state generation
- beam footprint motion
- receiver aperture
- all core pytest tests pass

### 2nd Completion

- STL loading
- ray-triangle intersection
- visible patch detection
- scatterer sampling on visible patch
- material assignment
- range/intensity image generation

### 3rd Completion

- car scene
- mirror/glass/paint/tire/retroreflector material distinction
- material contribution summary
- range image
- intensity image
- speckle map
- point cloud
- optional GPU batch acceleration
