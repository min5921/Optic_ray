# Material Model

## Goal

Define material-dependent reflection and roughness properties for 1550 nm FMCW LiDAR simulation.

## Required Materials

1. mirror
2. car_paint
3. glass
4. black_plastic
5. rubber
6. metal
7. license_plate
8. retroreflector
9. headlight_cover
10. tail_light
11. road_asphalt

## Material Fields

Each material should include:

- `name`
- `reflectivity`
- `specular_ratio`
- `diffuse_ratio`
- `retroreflective_ratio`
- `roughness_rms_m`
- `correlation_length_m`
- `absorption`
- `transmission`
- `polarization_dependent`
- `notes`

## Example JSON

```json
{
  "materials": [
    {
      "name": "mirror",
      "reflectivity": 0.95,
      "specular_ratio": 1.0,
      "diffuse_ratio": 0.0,
      "retroreflective_ratio": 0.0,
      "roughness_rms_m": 5e-9,
      "correlation_length_m": 1e-3,
      "absorption": 0.05,
      "transmission": 0.0,
      "polarization_dependent": false,
      "notes": "Idealized high-reflectivity mirror at 1550 nm."
    },
    {
      "name": "car_paint",
      "reflectivity": 0.35,
      "specular_ratio": 0.25,
      "diffuse_ratio": 0.75,
      "retroreflective_ratio": 0.0,
      "roughness_rms_m": 1e-6,
      "correlation_length_m": 20e-6,
      "absorption": 0.65,
      "transmission": 0.0,
      "polarization_dependent": false,
      "notes": "Simplified automotive paint model."
    },
    {
      "name": "retroreflector",
      "reflectivity": 0.8,
      "specular_ratio": 0.0,
      "diffuse_ratio": 0.1,
      "retroreflective_ratio": 0.9,
      "roughness_rms_m": 1e-7,
      "correlation_length_m": 100e-6,
      "absorption": 0.2,
      "transmission": 0.0,
      "polarization_dependent": false,
      "notes": "Use special retroreflective lobe model, not normal diffuse reflection."
    }
  ]
}
```

## Retroreflector

Retroreflector must not be modeled as ordinary diffuse or specular reflection.

It requires:

- angular acceptance
- return lobe toward incident direction
- return gain
- optional saturation/clipping

## Field Amplitude Weight

Reflectivity is a power coefficient.

Field amplitude must use:

```text
A_material = sqrt(reflectivity)
```
