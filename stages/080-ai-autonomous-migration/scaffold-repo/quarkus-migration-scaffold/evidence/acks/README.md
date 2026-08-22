# Stage-advance records (v2)

Human `ack_gate` is **out of day-one** (AD-019 K3: unfinished parents park
children). Do not commit live operator-named acks into the golden scaffold.

M1 findings presence is a gate record from `check-findings-handoff.py`, not a
human GO. M3 brief-identity is still a named Operator grant when dest is
provisioned later.

Keep `evidence/acks/` owner-writable in the live workspace so issuers can
write `*.ack.yaml`. Do not install a write-fence plugin until K2.
