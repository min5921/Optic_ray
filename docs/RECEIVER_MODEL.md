# Receiver Model

## Goal

Model receiver optics and coherent detection for FMCW LiDAR.

## Receiver Parameters

- `position`
- `direction`
- `aperture_diameter_m`
- `focal_length_m`
- `fov_rad`
- `detector_size_m`
- `optical_efficiency`
- optional `fiber_core_diameter_m`
- optional `fiber_na`
- optional `lo_mode_radius_m`

## Initial Model

For each scatterer:

1. check whether scatterer is within receiver FOV
2. calculate range to receiver
3. apply aperture collection efficiency
4. apply optical efficiency
5. apply material return weight
6. add complex field to coherent sum

## Collection Approximation

Power collection:

```text
P_collection ∝ aperture_area / R²
```

Field amplitude collection:

```text
A_collection ∝ sqrt(aperture_area) / R
```

## Coherent Mixer

The received field mixes with LO field.

Initial implementation may directly generate complex baseband beat signal.

Future implementation:

- LO power
- shot noise
- balanced detector
- IQ mixer
- fiber coupling
- LO mode overlap

## Receiver FOV

Scatterers outside receiver FOV must be rejected.

## Future Receiver Models

1. aperture plane field calculation
2. lens focusing
3. detector integration
4. single-mode fiber coupling efficiency
5. LO mode overlap integral
6. polarization sensitivity
