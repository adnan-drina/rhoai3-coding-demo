package com.redhat.coolstore.rest;

import com.redhat.coolstore.model.ProductListDto;
import com.redhat.coolstore.service.CatalogService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/cart")
public class CartEndpoint {
    private final CatalogService catalogService;

    public CartEndpoint(CatalogService catalogService) {
        this.catalogService = catalogService;
    }

    @GetMapping("/acceptance-check")
    public ProductListDto getProducts() {
        return new ProductListDto();
    }
}
