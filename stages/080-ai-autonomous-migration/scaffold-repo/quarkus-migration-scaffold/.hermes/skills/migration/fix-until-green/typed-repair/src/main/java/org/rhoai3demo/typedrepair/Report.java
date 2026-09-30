package org.rhoai3demo.typedrepair;

import java.util.ArrayList;
import java.util.List;
import java.util.TreeSet;

/**
 * What one recipe run decided, before and independently of any edit: the
 * outcome, the reasons, and the typed symbols it matched. A recipe decides its
 * outcome at the end of its scan (all cross-file facts collected) and edits
 * only when the outcome is {@link Outcome#APPLIED}; every other outcome leaves
 * every source file unchanged.
 */
public final class Report {

    public enum Outcome {
        APPLIED("applied"),
        ALREADY("already-in-required-form"),
        NOT_APPLICABLE("not-applicable"),
        UNRESOLVED("unresolved"),
        FAILED("failed");

        public final String wire;

        Outcome(String wire) {
            this.wire = wire;
        }
    }

    private Outcome outcome;
    private final List<String> reasons = new ArrayList<>();
    private final TreeSet<String> matched = new TreeSet<>();
    private final List<String> actions = new ArrayList<>();

    public synchronized void decide(Outcome o) {
        if (outcome == null) {
            outcome = o;
        }
    }

    /** The executor's own refusal of an inconsistent run: FAILED, whatever the recipe decided. */
    public synchronized void fail(String r) {
        outcome = Outcome.FAILED;
        reason(r);
    }

    /** Adopt another cycle's decision when this report has none yet (the first cycle's decision is the record). */
    public synchronized void adopt(Report other) {
        if (outcome != null || other == this) {
            return;
        }
        outcome = other.outcome();
        other.reasons().forEach(this::reason);
        other.matchedSymbols().forEach(this::matched);
        other.actions().forEach(this::action);
    }

    public synchronized Outcome outcome() {
        return outcome;
    }

    public synchronized void reason(String r) {
        if (!reasons.contains(r)) {
            reasons.add(r);
        }
    }

    public synchronized void matched(String symbol) {
        matched.add(symbol);
    }

    public synchronized void action(String a) {
        if (!actions.contains(a)) {
            actions.add(a);
        }
    }

    public synchronized List<String> reasons() {
        return new ArrayList<>(reasons);
    }

    public synchronized List<String> matchedSymbols() {
        return new ArrayList<>(matched);
    }

    public synchronized List<String> actions() {
        return new ArrayList<>(actions);
    }
}
