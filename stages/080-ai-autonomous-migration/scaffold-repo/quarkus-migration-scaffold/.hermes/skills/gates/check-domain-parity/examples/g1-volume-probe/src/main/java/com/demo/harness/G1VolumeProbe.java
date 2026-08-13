package com.demo.harness;

/**
 * Tooling-smoke probe for PIT dry-run plumbing only (AR-3.6 / AD-H §G.1).
 *
 * <p><b>Not</b> an acceptance operand. G-1 volume / kill-ratio for migration
 * ACCEPT must target product classes and product tests. Use
 * {@code G1_OPERAND=tooling_smoke} to exercise this class; default
 * {@code count-pit-dry-run.sh} excludes {@code com.demo.harness.*}.
 */
public final class G1VolumeProbe {
  private G1VolumeProbe() {}

  public static int clampNonNegative(int value) {
    if (value < 0) {
      return 0;
    }
    return value;
  }
}
