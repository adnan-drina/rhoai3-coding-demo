package com.demo.harness;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/** Trivial green suite for PIT dry-run volume (Research R1 / W2 §6). */
class G1VolumeProbeTest {
  @Test
  void clampsNegativeToZero() {
    assertEquals(0, G1VolumeProbe.clampNonNegative(-3));
  }

  @Test
  void passesThroughNonNegative() {
    assertEquals(7, G1VolumeProbe.clampNonNegative(7));
  }
}
