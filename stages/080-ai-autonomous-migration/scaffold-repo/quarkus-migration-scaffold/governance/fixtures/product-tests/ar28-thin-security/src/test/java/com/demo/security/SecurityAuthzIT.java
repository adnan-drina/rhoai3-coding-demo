package com.demo.security;

/** Fixture: security-only — AR-2.8 must REFUSE (missing boot/crud/db). */
public class SecurityAuthzIT {
    // AR28:security
    void anonymousIs401() {}
}
