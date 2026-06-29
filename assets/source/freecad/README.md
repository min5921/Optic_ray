# FreeCAD Sources

Place optional editable `.FCStd` source models here.

Recommended workflow:

1. keep each moving part or material region as a separate body;
2. choose a meaningful origin, especially for scanner pivots;
3. export each simulation body to `../../meshes/` as binary STL;
4. create a matching `.stl.yaml` metadata file;
5. check the imported bounding box, orientation, normals, and pivot in the 3D viewer.

FreeCAD backup files such as `.FCStd1` are ignored. Primary `.FCStd` files are not ignored.
