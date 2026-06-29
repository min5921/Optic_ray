# Coordinate, Placement, and STL Contract

- Status: Initial implementation contract
- Date: 2026-06-28

## 1. World Coordinate System

The simulator uses a right-handed world coordinate system:

- `+x`: forward, nominal target direction
- `+y`: left
- `+z`: up

All internal lengths are meters and all internal angles are radians.

## 2. Vector and Transform Convention

- vectors are column vectors
- rotations are active rotations
- homogeneous transforms are 4×4 matrices
- `T_A_from_B` maps coordinates expressed in frame B into frame A

```text
p_A = T_A_from_B @ p_B
T_world_from_component = T_world_from_assembly @ T_assembly_from_component
```

Directions and normals use the rotation block only. Normals are renormalized after transformation. Non-uniform scale is not permitted in a rigid component placement.

Internal rotation representation:

- normalized quaternion `[w, x, y, z]`, or
- orthonormal 3×3 rotation matrix

Euler angles may be accepted at the input boundary only when `euler_order` is explicit. They are converted immediately to an internal quaternion.

## 3. Component Frames

Each component can define:

- `component_frame`: primary rigid-body frame
- `mechanical_datums`: mount, pivot, mating, or measurement references
- `optical_ports`: beam connection references
- `surface_frames`: optical or reflective surface references
- `collision_geometry`: optional mechanical envelope
- `visual_geometry`: optional STL/STEP display geometry

Mechanical datums and optical ports are separate. Connecting two mounts does not imply perfect optical-axis alignment unless the catalog or assembly constraints explicitly state that relationship.

## 4. Optical Port Convention

An optical port contains:

- unique port ID
- local origin
- local `+z` nominal propagation direction
- local `+x/+y` transverse axes
- reference plane
- clear aperture
- input/output/bidirectional role
- optional accepted wavelength/profile/interface constraints

For an ordered transmit path, output-port `+z` and input-port `+z` are aligned in the same propagation direction.

Port-to-port placement may add:

- axial gap along the connected optical axis
- transverse offset in the port plane
- clocking rotation about the optical axis
- explicit angular misalignment

## 5. Placement Modes

### Absolute

The component transform is given relative to world or an assembly frame.

### Port-to-port

The component is placed so that its input port aligns with an upstream output port, then applies the requested gap, offset, clocking, and misalignment.

### Constraint-based

Reserved for a later placement solver. The initial implementation parses but does not solve arbitrary CAD-like constraint systems.

### Measured

The component transform is loaded from a measurement or calibration result. Nominal and measured transforms must remain distinguishable.

## 6. STL Import Contract

STL is a triangle mesh format and does not reliably carry units, material assignments, optical properties, component ports, pivots, or assembly constraints. Every imported STL therefore requires explicit metadata.

Initial STL rules:

- binary STL preferred
- one physical role per file
- one default material per target STL
- explicit `unit_scale_m` is mandatory
- explicit placement transform is mandatory unless identity is intentionally selected
- normals are validated and repaired or rejected according to policy
- open/non-manifold meshes generate warnings or errors depending on their role
- lens STL is mechanical/visual geometry only
- scanner STL requires an explicit pivot and rotation axis
- multi-material models are exported as separate STL files in the MVP

## 7. FreeCAD Workflow

Recommended project flow:

```text
FreeCAD .FCStd master
    ↓ export each part/body
binary STL mesh
    + matching .stl.yaml sidecar
    ↓
simulation asset loader
    ↓
validated SI-unit mesh + placement + role + material
```

FreeCAD source files may be kept under `assets/source/freecad/`. Exported meshes belong under `assets/meshes/`.

Before export:

1. place the model origin at a meaningful datum when practical;
2. place a scanner origin at its intended pivot when practical;
3. orient the model consistently with the project coordinate convention;
4. export separate bodies for different materials or moving parts;
5. choose tessellation fine enough for the optical footprint and intersection accuracy;
6. preserve the source filename and revision in the sidecar;
7. verify the imported bounding box and normals in the project viewer.

FreeCAD commonly models mechanical dimensions in millimeters, but the importer never assumes STL units. A millimeter export uses `unit_scale_m: 0.001` in the sidecar.

## 8. Mesh Roles

- `target`: participates in beam intersection and material return
- `scanner_surface`: moving reflective geometry with pivot and axis
- `optical_mechanical`: visualization/collision only; optical behavior comes from a separate prescription or catalog record
- `mount`: visualization/collision only
- `occluder`: visibility and shadowing only

## 9. Validation

On import, report:

- raw and SI-scaled bounding box
- triangle/vertex count
- manifold/open-edge status
- normal orientation summary
- selected role and material
- component transform
- scanner pivot/axis when applicable
- missing or assumed metadata
- source path and content hash

An STL is not accepted silently when its unit scale, role, or placement is unknown.
