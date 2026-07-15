# Shared encoder + separate curve heads (priority 3)

Five device parameters are encoded once. Separate IdVd and IdVg heads receive
the shared latent representation plus their fixed bias and predict the complete
curve. Target transforms remain head-specific. The baseline intentionally omits
intersection consistency loss so sharing and consistency can be evaluated in
separate experiments.
