# Workshop skill extensions (AD-011 / R-AD011.4)

Steer migration-agent behavior **without** editing `SOUL.md` or casually
forking the tip.

## Allowed surfaces (R-AD011.1)

1. **Overlay dir** on `skills.external_dirs` (e.g. copy this tree or add
   `~/workshop-skills/` in the Hermes profile).
2. **Name-shadow** under `$HERMES_HOME/skills/<skill-name>/` (local wins over
   external — official Hermes rule).
3. **Reference patches** — prefer editing/adding `references/*.md` (or tip
   `extensions/<skill>/references/*`) over rewriting `SKILL.md`.

## Tip additive overlay (R-AD011.2)

```
extensions/<skill-name>/references/<topic>.md
```

Example shipped: `extensions/spring-to-quarkus-patterns/references/jdbc-anti-essay.md`.

When a card hard-invokes `spring-to-quarkus-patterns` for JDBC work, the worker
must `skill_view` the **base** skill **and** the extension path. Hermes has no
`extends` merge — the second read is mandatory policy.

## Do not

- Edit `SOUL.md` to change migration procedure.
- Attach a new top-level skill per workflow component (OBJECT — R-AD011.3).
- Rely on MiniMax / model swap for “extensions to work.”
- Let workers `skill_manage` golden scaffold skills mid-run without
  `write_approval` (R-AD011.5).

## Falsifiers (demo failed)

See `migration/contracts/ad011-skill-extension.md` and Research pack Q7 —
extension unread, SOUL-only path, context explosion, or matrix bypass.
