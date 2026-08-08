package com.demo.harness;

/**
 * Specimen-free probe for G-1 volume floor (PIT dry-run Criterion 10).
 * Not product code — exists so {@code count-pit-dry-run.sh} has a green
 * unit + mutable bytecode when slice tests are incomplete/red.
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
