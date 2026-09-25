package org.acme.ledger.rest;

import jakarta.enterprise.context.ApplicationScoped;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import org.acme.ledger.dto.OwnerDto;

@ApplicationScoped
public class OwnerStore {
    private final Map<Integer, OwnerDto> owners = new ConcurrentHashMap<>();
    private final AtomicInteger ids = new AtomicInteger();

    public OwnerDto save(OwnerDto owner) {
        if (owner.getId() == null) {
            owner.setId(ids.incrementAndGet());
        }
        owners.put(owner.getId(), owner);
        return owner;
    }

    public OwnerDto find(int id) {
        return owners.get(id);
    }

    public List<OwnerDto> all() {
        return List.copyOf(owners.values());
    }
}
