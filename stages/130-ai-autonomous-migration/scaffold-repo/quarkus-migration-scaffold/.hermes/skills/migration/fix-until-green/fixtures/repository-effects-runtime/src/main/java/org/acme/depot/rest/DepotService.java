package org.acme.depot.rest;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.persistence.EntityManager;
import jakarta.transaction.Transactional;
import java.util.Collection;
import org.acme.depot.model.Crate;
import org.acme.depot.model.Kind;
import org.acme.depot.model.Label;
import org.acme.depot.model.Pallet;
import org.acme.depot.model.Stamp;
import org.acme.depot.repository.CrateRepository;
import org.acme.depot.repository.KindRepository;
import org.acme.depot.repository.LabelRepository;

// one transaction per call, as the source's transactional service: the
// controller reads (detached), changes, and saves in another transaction --
// every write effect crosses a transaction boundary before it is read back
@ApplicationScoped
public class DepotService {
    @Inject
    CrateRepository crates;   // the GENERATED Spring Data repository (the delegate is @Typed to itself)

    @Inject
    LabelRepository labels;

    @Inject
    EntityManager em;

    @Transactional
    public Collection<Crate> allCrates() {
        return crates.findAll();
    }

    @Transactional
    public Crate findCrate(int id) {
        return crates.findById(id);
    }

    @Transactional
    public Crate saveCrate(Crate crate) {
        for (Pallet p : crate.pallets) {
            p.crate = crate;
        }
        crates.save(crate);
        return crate;
    }

    @Transactional
    public void deleteCrate(Crate crate) {
        crates.delete(crate);
    }

    @Transactional
    public Pallet findPallet(int id) {
        return em.find(Pallet.class, id);
    }

    @Transactional
    public boolean link(int palletId, int labelId) {
        Pallet p = em.find(Pallet.class, palletId);
        Label l = em.find(Label.class, labelId);
        if (p == null || l == null) {
            return false;
        }
        p.labels.add(l);
        return true;
    }

    @Transactional
    public Label findLabel(int id) {
        return labels.findById(id);
    }

    @Transactional
    public Label saveLabel(Label label) {
        labels.save(label);
        return label;
    }

    @Transactional
    public void deleteLabel(Label label) {
        labels.delete(label);
    }

    @Inject
    KindRepository kinds;

    @Transactional
    public Kind findKind(int id) {
        return kinds.findById(id);
    }

    @Transactional
    public Kind saveKind(Kind kind) {
        kinds.save(kind);
        return kind;
    }

    @Transactional
    public void deleteKind(Kind kind) {
        kinds.delete(kind);
    }

    @Transactional
    public boolean setKind(int palletId, int kindId) {
        Pallet p = em.find(Pallet.class, palletId);
        Kind k = em.find(Kind.class, kindId);
        if (p == null || k == null) {
            return false;
        }
        p.kind = k;
        return true;
    }

    @Transactional
    public Stamp addStamp(int palletId, String name) {
        Pallet p = em.find(Pallet.class, palletId);
        if (p == null) {
            return null;
        }
        Stamp s = new Stamp();
        s.name = name;
        s.pallet = p;
        em.persist(s);
        return s;
    }

    @Transactional
    public Stamp findStamp(int id) {
        return em.find(Stamp.class, id);
    }
}
