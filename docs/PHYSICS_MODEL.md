# Physics Model

## Core Principle

The simulator uses a hybrid model:

1. geometric optics for visibility, scanner steering, mirror reflection, and STL intersection
2. coherent field summation for FMCW LiDAR signal and speckle

Ray tracing is not the final signal model.

## Correct Speckle Computation

For scatterers indexed by `i`:

```text
E_rx(t) = Σ_i A_i exp(j(2π f_bi t + φ_i))
P_rx(t) = |E_rx(t)|²
```

Where:

- `A_i`: field amplitude contribution
- `f_bi`: FMCW beat frequency of scatterer `i`
- `φ_i`: total phase of scatterer `i`

Do not compute speckle by summing powers:

```text
P_rx = Σ_i P_i
```

That removes coherent interference and does not produce real speckle fading.

## Field and Power

Use the convention:

```text
P ∝ |E|²
E ∝ sqrt(P)
```

Therefore:

- material reflectivity affects power
- field amplitude should be weighted by sqrt(reflectivity)

Example:

```text
A_material = sqrt(material_reflectivity)
```

## Scatterer Phase

For a monostatic LiDAR, the optical round-trip phase is:

```text
φ_range = 4πR / λ
```

Roughness height `h` contributes:

```text
φ_rough = 4πh / λ
```

Total phase:

```text
φ_i = 4πR_i / λ + φ_rough_i + φ_material_i
```

## Geometric Visibility

Geometric optics is used to compute:

- surface hit point
- surface normal
- incidence angle
- occlusion
- mirror reflection direction
- scanner output direction
- beam footprint location

## Mirror Reflection

For incident direction `D` and surface normal `N`:

```text
R = D - 2(D·N)N
```

All vectors must be normalized.

## Beam Footprint

Beam footprint determines which scatterers are illuminated and with what amplitude weight.

For a Gaussian beam:

```text
I(x, y) = I0 exp(-2(x²/w_x² + y²/w_y²))
A(x, y) ∝ exp(-(x²/w_x² + y²/w_y²))
```

At oblique incidence, footprint expands approximately by:

```text
1 / cos(theta_incidence)
```

## Fixed Scatterer Map

The target rough surface must have fixed scatterer positions and roughness phases.

Scanner movement should move the beam footprint over the same scatterer map.

Do not regenerate scatterer phases per pixel.
