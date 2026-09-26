# Monitoring safety

Operational checks should stay read-only and avoid changing service state. Keep restart or repair actions separate from health probes so monitoring cannot accidentally modify a live deployment.
