from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared across app/main.py (registration) and individual routers (the
# @limiter.limit(...) decorators) — a single module-level instance avoids
# circular imports between main.py and the routers it includes.
#
# Keyed by client IP: there's no login yet, so per-account limiting isn't
# possible. This is a stopgap against runaway cost/abuse until accounts
# exist, not a strong guarantee (shared IPs, VPNs can evade it).
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
