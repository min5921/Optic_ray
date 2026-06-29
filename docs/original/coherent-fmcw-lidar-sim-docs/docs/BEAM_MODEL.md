# Beam Model

## Goal

Use Beam source, not Ray source.

The beam model must represent:

- wavelength
- optical power
- waist
- M²
- divergence
- elliptical beam
- line beam
- beam local coordinate frame
- target footprint

## Gaussian Beam with M²

Parameters:

- `wavelength_m`
- `power_w`
- `waist_radius_x_m`
- `waist_radius_y_m`
- `waist_position_m`
- `m2_x`
- `m2_y`
- `polarization`
- `center`
- `direction`

Divergence:

```text
θ_x ≈ M²_x λ / (π w0_x)
θ_y ≈ M²_y λ / (π w0_y)
```

Effective Rayleigh length:

```text
zR_x = π w0_x² / (M²_x λ)
zR_y = π w0_y² / (M²_y λ)
```

Beam radius at distance z:

```text
w_x(z) = w0_x sqrt(1 + ((z - z0)/zR_x)^2)
w_y(z) = w0_y sqrt(1 + ((z - z0)/zR_y)^2)
```

Gaussian intensity:

```text
I(x, y, z) = I0 exp(-2(x²/w_x(z)² + y²/w_y(z)²))
```

Field amplitude weight:

```text
A(x, y, z) ∝ exp(-(x²/w_x(z)² + y²/w_y(z)²))
```

## Beam Types

Initial:

1. circular Gaussian beam
2. elliptical Gaussian beam
3. line beam

Future:

1. top-hat beam
2. measured beam profile
3. astigmatic beam
4. multimode beam approximation

## Beam Local Frame

Each beam must carry a local coordinate frame:

- z': propagation direction
- x': horizontal transverse axis
- y': vertical transverse axis

This is necessary for:

- elliptical beam
- line beam
- beam footprint projection
- scanner-induced line rotation

## BeamState

`BeamState` must include:

- `time_s`
- `origin`
- `direction`
- `local_x_axis`
- `local_y_axis`
- `wavelength_m`
- `power_w`
- `waist_radius_x_m`
- `waist_radius_y_m`
- `m2_x`
- `m2_y`
- `divergence_x_rad`
- `divergence_y_rad`
- `polarization`
- `optical_path_length_m`
- `accumulated_transmission`
