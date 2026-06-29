# Simulation Meshes

Place exported STL meshes and their sidecar metadata here.

Example:

```text
target_panel.stl
target_panel.stl.yaml
scan_mirror.stl
scan_mirror.stl.yaml
```

Initial limitations:

- one role and one default material per STL;
- units must be declared in the sidecar;
- placement must be explicit;
- scanner meshes require pivot and axis metadata;
- lens meshes are mechanical/visual geometry only.

Copy [`mesh_metadata.example.yaml`](mesh_metadata.example.yaml) when adding a mesh.
