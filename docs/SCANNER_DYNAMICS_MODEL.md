# Scanner Dynamics Model

## Goal

Model actual scanner motion, not only static ray direction.

The scanner model must answer:

1. At time `t`, what is the mirror angle?
2. At time `t`, what is the outgoing beam direction?
3. At time `t`, where does the beam hit the scene?
4. What is the beam footprint on the target?
5. For a line beam, what is the line orientation on the target?
6. How does scanner motion affect speckle decorrelation?
7. How does scanner motion define FMCW pixel timing?

## Scanner Types

Initial support:

1. Raster scanner
2. Galvo scanner
3. MEMS scanner
4. Polygon mirror
5. Static flat mirror

Future support:

1. tilted polygon mirror
2. two-axis coupled scanner
3. scanner with measured calibration table

## Coordinate Convention

Global:

- x: forward
- y: lateral
- z: up

Beam local:

- z': beam propagation direction
- x': horizontal transverse axis
- y': vertical transverse axis

Scanner mirror:

- mirror center
- mirror normal `N(t)`
- rotation axis
- mechanical mirror angle `theta_m(t)`
- optical scan angle `theta_out(t)`

For small mirror angle changes:

```text
theta_optical ≈ 2 * theta_mirror
```

## Time Model

Each scan sample or pixel has:

- time `t`
- scanner state
- outgoing BeamState
- target hit point
- received FMCW waveform or peak result

The scanner must support:

1. continuous evaluation by time
2. discrete pixel sampling
3. frame-based scan generation

Example scan parameters:

- frame_rate_hz = 10
- horizontal_fov_deg = 120
- vertical_fov_deg = 30
- horizontal_pixels = 512
- vertical_pixels = 128
- chirps_per_pixel = 1
- samples_per_chirp = 4096

## ScannerState

Create a `ScannerState` dataclass:

- `time_s`
- `frame_index`
- `line_index`
- `column_index`
- `pixel_index`
- `mirror_angle_x_rad`
- `mirror_angle_y_rad`
- `mirror_angular_velocity_x_rad_s`
- `mirror_angular_velocity_y_rad_s`
- `mirror_normal`
- `input_beam_direction`
- `output_beam_direction`
- `output_origin`
- `local_x_axis`
- `local_y_axis`

## BeamState After Scanner

The scanner receives an input BeamState and returns an output BeamState.

Output BeamState includes:

- updated origin
- updated direction
- updated local frame
- updated optical path length
- accumulated transmission
- scanner loss
- timestamp

## Scan Patterns

### Raster Scan

Parameters:

- horizontal_fov_rad
- vertical_fov_rad
- horizontal_pixels
- vertical_pixels
- frame_rate_hz
- bidirectional_scan

At pixel `(row, col)`:

```text
theta_x = mapped horizontal angle
theta_y = mapped vertical angle
```

### Triangle Scan

For galvo-like line scanning:

```text
theta_x(t) = triangle_wave(A_x, f_x, t)
theta_y(t) = slow waveform
```

### Sinusoidal Scan

For resonant MEMS or galvo:

```text
theta_x(t) = A_x sin(2π f_x t + phi_x)
theta_y(t) = A_y sin(2π f_y t + phi_y)
```

### Polygon Scan

Parameters:

- facets
- rotation_rate_hz
- facet_tilt_error_rad
- facet_angle_error_rad
- effective_scan_fov_rad
- line_rate_hz

The output beam direction depends on the active facet normal.

### Tilted Polygon Mirror

Support later:

- polygon rotation
- facet normal
- facet tilt
- reflected beam direction
- line beam orientation rotation
- scan line curvature or rotation

## Beam Footprint on Target

For each BeamState and target surface, calculate beam footprint.

Inputs:

- BeamState
- hit point
- target surface normal
- beam radius at range
- beam local frame
- incidence angle

Outputs:

- footprint center
- footprint major radius
- footprint minor radius
- footprint orientation vector on surface
- incidence angle
- projected area scale
- line orientation, if line beam

At oblique incidence:

```text
footprint size along incidence direction increases by 1/cos(theta_incidence)
```

For line beam:

- line length
- line width
- line direction on target surface
- line rotation due to scanner/mirror orientation

## Scanner Error Model

Optional imperfections:

1. pointing jitter
2. mirror angle noise
3. facet-to-facet error
4. wobble
5. nonlinear scan angle
6. timing jitter
7. line bow
8. line rotation
9. scanner aperture clipping

Error parameters:

- angle_jitter_rms_rad
- timing_jitter_rms_s
- facet_angle_error_rms_rad
- facet_tilt_error_rms_rad
- mirror_surface_roughness_m
- scanner_aperture_diameter_m

## Speckle Coupling

Scanner motion changes the beam footprint.

Critical rule:

- target surface has fixed scatterer positions and roughness phases
- beam footprint moves over fixed scatterers
- scatterer weights change according to beam profile
- speckle decorrelation emerges naturally

Do not regenerate scatterers per pixel.

## FMCW Pixel Timing

Each pixel has:

- chirp start time
- chirp duration
- scanner state during chirp

Initial approximation:

- scanner state is constant during one chirp

Future advanced model:

- scanner moves during chirp
- beam footprint changes during acquisition
- intra-chirp amplitude/phase modulation is simulated
