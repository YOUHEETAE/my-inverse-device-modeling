# Coordinate DeepONet (priority 3)

The branch network encodes normalized device/bias features and the trunk network
encodes a requested sweep voltage. Their latent dot product predicts current at
each coordinate, allowing inference on voltage grids not used during training.
