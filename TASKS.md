# TASKS

## Phase 1: FMCW Single Target CPU Reference

- [ ] Create project structure
- [ ] Add `pyproject.toml` and `requirements.txt`
- [ ] Implement `src/lidarsim/constants.py`
- [ ] Implement `src/lidarsim/fmcw/chirp.py`
- [ ] Implement `src/lidarsim/fmcw/beat_signal.py`
- [ ] Implement `src/lidarsim/processing/fft_processing.py`
- [ ] Add `examples/01_single_target_fmcw.py`
- [ ] Add `tests/test_fmcw_range.py`

## Phase 2: Gaussian Beam + M²

- [ ] Implement `src/lidarsim/beam/gaussian_beam.py`
- [ ] Implement `src/lidarsim/beam/beam_frame.py`
- [ ] Add `examples/02_gaussian_beam_m2.py`
- [ ] Add `tests/test_gaussian_beam.py`

## Phase 3: ABCD Lens + Aperture

- [ ] Implement `src/lidarsim/optics/abcd.py`
- [ ] Implement `src/lidarsim/optics/free_space.py`
- [ ] Implement `src/lidarsim/optics/thin_lens.py`
- [ ] Implement `src/lidarsim/optics/aperture.py`
- [ ] Add `examples/03_thin_lens_abcd.py`
- [ ] Add `examples/04_aperture_clipping.py`
- [ ] Add `tests/test_abcd_lens.py`
- [ ] Add `tests/test_aperture_clipping.py`

## Phase 4: Rough Surface Speckle CPU Reference

- [ ] Implement `src/lidarsim/scatter/scatterer.py`
- [ ] Implement `src/lidarsim/scatter/rough_surface.py`
- [ ] Implement `src/lidarsim/scatter/speckle.py`
- [ ] Add `examples/05_rough_surface_speckle.py`
- [ ] Add `examples/06_scan_speckle_decorrelation.py`
- [ ] Add `tests/test_speckle_statistics.py`

## Phase 5: Receiver Aperture

- [ ] Implement `src/lidarsim/receiver/receiver.py`
- [ ] Implement `src/lidarsim/receiver/aperture_collection.py`
- [ ] Add `tests/test_receiver_aperture.py`

## Phase 6: Scanner Dynamics

- [ ] Implement `src/lidarsim/scanner/scanner_state.py`
- [ ] Implement `src/lidarsim/scanner/scan_pattern.py`
- [ ] Implement `src/lidarsim/scanner/footprint.py`
- [ ] Implement raster scanner model
- [ ] Implement triangle scanner model
- [ ] Implement sinusoidal scanner model
- [ ] Implement polygon scanner model
- [ ] Add `examples/11_raster_scanner_beam_motion.py`
- [ ] Add `examples/12_triangle_galvo_scanner.py`
- [ ] Add `examples/13_polygon_scanner_facets.py`
- [ ] Add `examples/14_line_beam_rotation.py`

## Phase 7: Scanner-Driven Speckle Decorrelation

- [ ] Fixed scatterer map on rough target
- [ ] Moving beam footprint from scanner
- [ ] Scatterer weights updated by footprint movement
- [ ] Speckle decorrelation without regenerating random phases
- [ ] Add `examples/15_scanner_speckle_decorrelation.py`
- [ ] Add `examples/16_scanner_motion_during_chirp.py`

## Phase 8: Compute Backend Abstraction

- [ ] Implement `src/lidarsim/compute/backend.py`
- [ ] Implement `src/lidarsim/compute/batching.py`
- [ ] Optional: add CuPy backend
- [ ] Optional: add Torch backend
- [ ] Add `examples/17_gpu_fmcw_batch_fft.py`

## Phase 9: STL Visible Patch

- [ ] Implement `src/lidarsim/scene/stl_loader.py`
- [ ] Implement `src/lidarsim/scene/ray_intersection.py`
- [ ] Implement `src/lidarsim/scene/visible_patch.py`
- [ ] Add `examples/08_stl_visible_patch.py`

## Phase 10: Material Database

- [ ] Implement `src/lidarsim/materials/material.py`
- [ ] Implement `src/lidarsim/materials/material_db.py`
- [ ] Implement `src/lidarsim/materials/retroreflector.py`
- [ ] Add `assets/materials/materials_1550nm.json`
- [ ] Add `tests/test_material_db.py`

## Phase 11: Car / Mirror / Retroreflector Scene

- [ ] Implement simple car scene
- [ ] Add material assignment
- [ ] Generate range image
- [ ] Generate intensity image
- [ ] Generate speckle map
- [ ] Generate point cloud
- [ ] Add material contribution summary
- [ ] Add `examples/09_car_material_scan.py`
- [ ] Add `examples/10_generate_range_image.py`
