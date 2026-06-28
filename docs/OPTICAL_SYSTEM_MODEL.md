# Optical System Model

## Goal

Model transmitter and receiver optical systems with modular elements.

Initial implementation uses paraxial optics and ABCD matrices.

## Supported Elements

1. FreeSpace
2. ThinLens
3. Aperture
4. FlatMirror
5. ScannerMirror
6. BeamExpander

## ABCD Matrix

Free space length `L`:

```text
[1  L]
[0  1]
```

Thin lens focal length `f`:

```text
[1    0]
[-1/f 1]
```

Gaussian q-parameter propagation:

```text
q_out = (A q_in + B) / (C q_in + D)
```

## Aperture Clipping

An aperture has:

- clear aperture diameter
- transmission
- position

The simulator should estimate clipping loss for a Gaussian beam.

If aperture radius is much larger than beam radius, loss should be nearly zero.

If aperture radius is smaller than beam radius, transmitted power should decrease.

## Mirror

Flat mirror reflection:

```text
R = D - 2(D·N)N
```

Mirror should also apply:

- reflectivity
- aperture clipping
- optional surface error

## Beam Expander

Parameters:

- magnification
- transmission

Effect:

- beam radius increases by magnification
- divergence decreases by magnification

## OpticalSystem

An `OpticalSystem` object is an ordered chain of elements.

Input:

- BeamState

Output:

- BeamState
- accumulated transmission
- clipping report
- debug report

## Lens Modeling Levels

### Level 1: Thin Lens

Use:

- focal length
- clear aperture
- transmission

### Level 2: Thick Lens

Use:

- front radius
- back radius
- center thickness
- refractive index
- diameter

### Level 3: Sequential Ray Tracing

Use:

- surface sag
- asphere coefficients
- dispersion
- aperture stop
- tilt/decenter

### Level 4: Physical Optics

Use:

- wavefront
- aperture diffraction
- Fresnel propagation
- PSF
- fiber coupling

Initial implementation should stay at Level 1.
