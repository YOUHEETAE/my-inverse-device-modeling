# Coordinate field MLP

This is the first trainable field-map baseline. Two independent residual MLPs
map global device parameters, normalized coordinates, region identity, and the
known local `NetDoping` value to either node-centered or element-centered
fields.

- Node outputs: `Potential`, `Electrons`, `Holes`, `USRH`
- Element outputs: electric-field and electron/hole-current x/y components
- Training sampling: equal point counts per device and mesh region
- Selection: validation early stopping; test cases remain unopened

The saved `model.pt` checkpoint contains the architecture, weights, feature
scaler, field names, and fitted target transforms. The adjacent JSON files make
the same preprocessing state inspectable without loading PyTorch.

This model is a baseline, not the final selected field-map architecture.
Element current density, especially its y component, is expected to require
separate heads, derivative-aware constraints, or a more mesh-aware model in the
next optimization stage.
