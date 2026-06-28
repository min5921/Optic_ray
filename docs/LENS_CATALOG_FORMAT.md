# Lens Catalog Format

## Goal

Allow commercial lens specifications to be inserted into the simulation.

The initial model is thin lens based.

## Important Rule

Do not use STL lens geometry alone to calculate optical focusing.

A lens requires optical specifications such as:

- focal length
- clear aperture
- refractive index
- center thickness
- aspheric coefficients
- coating
- transmission

STL or STEP geometry is useful for mechanical visualization but insufficient for optical simulation.

## JSON Format

```json
{
  "lenses": [
    {
      "id": "generic_asphere_8mm_1550",
      "vendor": "generic",
      "type": "aspheric_lens",
      "model_level": "thin_lens",
      "focal_length_m": 0.008,
      "diameter_m": 0.006,
      "clear_aperture_m": 0.0055,
      "center_thickness_m": 0.003,
      "na": 0.5,
      "coating_range_nm": [1050, 1700],
      "transmission": 0.98
    }
  ]
}
```

## Model Levels

### Level 1: Thin Lens

Fields:

- focal length
- clear aperture
- transmission

### Level 2: Thick Lens

Additional fields:

- front radius
- back radius
- center thickness
- refractive index

### Level 3: Aspheric Lens

Additional fields:

- conic constant
- aspheric coefficients
- material dispersion

### Level 4: Sequential Surface Import

Future support:

- Zemax export
- Code V export
- custom surface list
