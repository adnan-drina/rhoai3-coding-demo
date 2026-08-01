package org.springframework.samples.petclinic.service;

import org.springframework.cache.annotation.Cacheable;

public class CachedVets {
    @Cacheable("vets")
    public String load() {
        return "x";
    }
}
