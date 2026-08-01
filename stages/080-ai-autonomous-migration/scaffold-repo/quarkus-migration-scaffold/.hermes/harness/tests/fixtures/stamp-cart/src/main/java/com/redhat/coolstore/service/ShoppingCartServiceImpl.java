package com.redhat.coolstore.service;

import java.util.HashMap;
import javax.inject.Singleton;

@Singleton
public class ShoppingCartServiceImpl {
    private HashMap<String, Object> carts = new HashMap<>();

    public void addItem(String id) {
        carts.put(id, id);
    }
}
