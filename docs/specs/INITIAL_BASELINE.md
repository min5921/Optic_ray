# Initial Simulation Baseline

- Status: Accepted initial defaults
- Date: 2026-06-28
- Purpose: Phase 0-5 analytical validation before real hardware specifications are available
- Important: These values are simulation reference values, not claims about any commercial product.

## 1. Modeling Scope

The first implementation uses the native Python CPU model and does not require Zemax, CODE V, or OpticStudio.

Included:

- one transmit path
- Gaussian point beam and elliptical Gaussian line-beam preset
- ideal thin-lens fiber collimator
- absolute and port-to-port component placement
- one-axis flat-mirror scanner
- flat diffuse target
- virtual monostatic circular receiver aperture
- received optical power at the receiver aperture
- Matplotlib validation plots and a PyVista 3D layout viewer
- FreeCAD-exported STL geometry with YAML sidecar metadata

Deferred:

- area top-hat diffraction
- full CAD constraint solver
- general Zemax/CODE V import
- beamsplitter and multiple optical paths
- transparent BSDF and ghost reflections
- detector photocurrent/noise/SNR
- coherent FMCW and speckle
- GPU acceleration

## 2. Coordinate and Placement Baseline

- right-handed world coordinate system
- `+x`: forward toward the nominal target
- `+y`: left
- `+z`: up
- internal length: meter
- internal angle: radian
- column vectors
- active rotations
- transform naming: `T_destination_from_source`
- internal quaternion order: `[w, x, y, z]`
- optical-port local `+z`: nominal propagation direction
- internal placement: `float64`

The detailed contract is in [`COORDINATES_AND_PLACEMENT.md`](COORDINATES_AND_PLACEMENT.md).

## 3. Source Baseline

### Point-beam reference

| Parameter | Initial value |
|---|---:|
| Source type | Fiber Gaussian reference |
| Wavelength | 1550 nm |
| Optical power | 10 mW |
| Fiber mode-field diameter | 10 µm |
| Waist radius | 5 µm |
| M² | 1.0 |
| Polarization | Unspecified scalar |
| Spectral model | Single wavelength |

### Line-beam reference

The first line beam is a numerical elliptical-Gaussian preset at its reference plane. It does not claim to model a Powell lens or a specific commercial line generator.

| Parameter | Initial value |
|---|---:|
| Optical power | 10 mW |
| Long-axis 1/e² radius | 3.0 mm |
| Short-axis 1/e² radius | 0.25 mm |
| M², long/short axes | 1.0 / 1.0 |
| Orientation | Local +x transverse axis |

Area-beam propagation is deferred until a Fresnel or measured-profile model is available.

## 4. Ideal Collimator Baseline

| Parameter | Initial value |
|---|---:|
| Model level | Level 1, paraxial specification |
| Lens type | Ideal thin lens |
| Effective focal length | 20 mm |
| Clear-aperture diameter | 10 mm |
| Power transmission | 1.0 |
| Source-waist placement | Front focal plane |
| Design wavelength | 1550 nm |

For the point-beam reference, the expected collimated 1/e² radius near the lens is approximately:

```text
w_out ≈ wavelength × focal_length / (pi × w_source)
      ≈ 1.97 mm
```

The expected full 1/e² diameter is approximately 3.95 mm. This is an analytical validation value for the ideal model.

## 5. Scanner Baseline

| Parameter | Initial value |
|---|---:|
| Scanner type | One-axis ideal flat mirror |
| Mirror size | 20 mm × 20 mm |
| Pivot | Mirror center |
| Rotation axis | World +y |
| Mechanical angle | ±5 degrees |
| Motion | 10 Hz triangle wave |
| Samples per line | 101 |
| Reflectivity | 1.0 |
| Dynamic lag/jitter | Disabled |

Reference placement:

- source and collimator deliver the incident beam along world `+z`
- scanner pivot is at world `[0, 0, 0]` m
- zero-angle mirror normal is `[-sqrt(0.5), 0, sqrt(0.5)]`
- zero-angle reflected beam travels along world `+x`
- scanner rotation about `+y` produces an approximately two-times optical scan-angle change near the reference pose

## 6. Target Baseline

| Parameter | Initial value |
|---|---:|
| Geometry | Flat rectangular plane |
| Plane center | `[10, 0, 0]` m |
| Plane normal | `[-1, 0, 0]` |
| Size | 4 m × 4 m |
| Material | Ideal Lambertian diffuse |
| Hemispherical reflectivity | 0.20 |
| Occlusion | Disabled for the analytical case |

The plane is large enough to contain the nominal ±10-degree optical scan at 10 m.

## 7. Receiver Baseline

| Parameter | Initial value |
|---|---:|
| Architecture | Virtual monostatic receiver |
| Aperture center | `[0, 0, 0]` m |
| Aperture normal | World `+x` |
| Aperture diameter | 25 mm |
| Optical efficiency | 0.80 |
| FOV | 25 degrees full angle |
| Detector model | Deferred |
| Primary result | Optical power at receiver aperture |

The virtual co-location avoids modeling a beamsplitter and reverse scanner path in the first radiometric validation. A physical transmit/receive assembly replaces it when real hardware is specified.

## 8. Numerical and Validation Baseline

| Item | Initial target |
|---|---:|
| Geometry dtype | float64 |
| Coherent dtype, when added | complex128 |
| Transform position error | < 1e-9 m |
| Unit-vector norm error | < 1e-12 |
| Port angular alignment error | < 1e-9 rad |
| Gaussian radius relative error | < 0.1% |
| Beam-power normalization error | < 0.1% |
| Analytical radiometric power error | < 1% |
| Random seed | 0 when stochastic models are introduced |

These are software-validation tolerances. Real-product accuracy will be limited by catalog, CAD, material, alignment, and measurement uncertainty.

## 9. Initial Performance Baseline

- CPU/NumPy reference implementation
- one scan line
- 101 scan samples
- one target plane
- one material
- no surface scatterer cloud in the radiometric MVP
- results rendered as static plots and one interactive 3D layout

## 10. Override Policy

Every initial value must be replaceable in a versioned configuration file. When real equipment data becomes available:

1. preserve this baseline as a regression example;
2. create a separate hardware configuration;
3. record the source of every replacement value;
4. never overwrite a measured or catalog value with an undocumented assumption.
