package com.redhat.coolstore.service;

import org.springframework.cache.annotation.Cacheable;

public class CatalogCache {
    @Cacheable("products")
    public String load() {
        return "x";
    }
}
