# Profiles — build-time vs runtime

## Built-ins and syntax

Built-in profiles: `dev` (dev mode), `test` (tests), `prod` (default otherwise).
Custom profiles need only a `%name.` prefix (or `application-{name}.properties`)
— no registration step.

Syntax: `%{profile}.config.name=value`. Multiple active:
`quarkus.profile=common,dev`.

## Activation order (`ProfileManager`)

1. `quarkus.profile` system property  
2. `QUARKUS_PROFILE` environment variable  
3. Default runtime profile baked at build time  
4. Launch-mode default  

System property wins over the environment variable.

## Default runtime profile (load-bearing)

The default Quarkus runtime profile is **the profile used to build the
application**. Default builds use `prod`. Starting the same jar with different
`QUARKUS_PROFILE` values only changes **runtime-overridable** keys; build-time
keys stay fixed to the build.

## Build-time vs runtime

Some keys take effect only at build (augmentation). Changing them requires a
rebuild. Config option tables mark build-time keys with a lock icon — use that,
do not guess. `@IfBuildProfile` is likewise build-time (which beans exist).

## Not Spring

Spring Boot largely resolves `application-{profile}.properties` at startup.
Quarkus's `%profile.` / profile-aware files are a **syntactic** cousin; the
**semantic** difference is the build-time/runtime split. Do not design
"one properties file per environment, always switchable on a single jar"
unless every differing key is actually runtime-overridable.
