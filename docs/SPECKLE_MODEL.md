# Speckle Model

## Goal

Model coherent speckle in FMCW LiDAR from rough surfaces.

Speckle appears when many scatterers return coherent fields with different phases.

## Coherent Sum

For scatterers:

```text
E_rx(t) = Σ_i A_i exp(j(2π f_bi t + φ_i))
```

The intensity is:

```text
I_rx(t) = |E_rx(t)|²
```

## Roughness Phase

Surface height `h_i`:

```text
φ_rough_i = 4πh_i / λ
```

Total phase:

```text
φ_i = 4πR_i / λ + φ_rough_i + φ_material_i
```

## Scatterer Identity

Scatterer identity must remain fixed across scan positions.

The beam footprint moves over the same scatterer map.

This allows speckle correlation and decorrelation to emerge naturally.

## Implementation Levels

### Level 1: Random Phase Scatterers

- Scatterers have fixed random phase
- Quick MVP
- Useful for checking coherent sum

### Level 2: Roughness Height Scatterers

- Scatterers have height values
- Phase from `4πh/λ`
- Material roughness RMS controls variation

### Level 3: Correlated Roughness Map

- Surface roughness has spatial correlation length
- Neighboring scatterers have correlated heights

### Level 4: Aperture Plane Field Propagation

- Field propagated to receiver aperture
- Enables more realistic aperture speckle
- Expensive

## Speckle Decorrelation

As the beam footprint moves:

- small movement: highly correlated speckle
- large movement: decorrelated speckle

Implementation:

1. generate fixed scatterer map
2. evaluate Gaussian beam weight at each scan position
3. coherent sum weighted scatterers
4. calculate FFT peak amplitude
5. compute correlation vs scan displacement

## Expected Behavior

For fixed target range:

- range peak position remains mostly constant
- peak amplitude fluctuates with scan position
- larger roughness creates stronger fluctuation
- larger beam spot may reduce fluctuation by averaging more scatterers
